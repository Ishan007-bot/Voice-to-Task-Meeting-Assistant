"""Task Endpoints"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.repositories.meeting import MeetingRepository
from app.repositories.task import TaskRepository
from app.repositories.integration import IntegrationRepository
from app.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
    TaskBulkAction,
    TaskSyncRequest,
    TaskSyncResult,
)
from app.workers.tasks import sync_task_to_external
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/meeting/{meeting_id}", response_model=TaskListResponse)
async def list_meeting_tasks(
    meeting_id: str,
    status: Optional[TaskStatus] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """List all tasks for a specific meeting."""
    meeting_repo = MeetingRepository(db)
    task_repo = TaskRepository(db)
    
    # Verify meeting access
    meeting = await meeting_repo.get_by_id(meeting_id)
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    offset = (page - 1) * page_size
    
    tasks = await task_repo.get_meeting_tasks(
        meeting_id=meeting_id,
        status=status,
        skip=offset,
        limit=page_size,
    )
    
    total = await task_repo.count_meeting_tasks(meeting_id, status)
    
    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/all", response_model=TaskListResponse)
async def list_all_tasks(
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """List all tasks for the current user across all meetings."""
    task_repo = TaskRepository(db)
    
    offset = (page - 1) * page_size
    
    tasks = await task_repo.get_user_tasks(
        user_id=current_user.id,
        status=status,
        priority=priority,
        skip=offset,
        limit=page_size,
    )
    
    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=len(tasks),  # Would need proper count query
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Manually create a new task."""
    meeting_repo = MeetingRepository(db)
    task_repo = TaskRepository(db)
    
    # Verify meeting access
    meeting = await meeting_repo.get_by_id(task_data.meeting_id)
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    task = await task_repo.create({
        **task_data.model_dump(),
        "status": TaskStatus.PENDING,  # Manually created = already reviewed
        "is_user_modified": True,
    })
    
    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Get task by ID."""
    task_repo = TaskRepository(db)
    meeting_repo = MeetingRepository(db)
    
    task = await task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    # Verify access through meeting
    meeting = await meeting_repo.get_by_id(task.meeting_id)
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Update a task."""
    task_repo = TaskRepository(db)
    meeting_repo = MeetingRepository(db)
    
    task = await task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    meeting = await meeting_repo.get_by_id(task.meeting_id)
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    update_data = task_update.model_dump(exclude_unset=True)
    
    # Track if user modified the task
    if update_data:
        update_data["is_user_modified"] = True
        if "title" in update_data and task.original_title is None:
            update_data["original_title"] = task.title
    
    updated = await task_repo.update(task_id, update_data)
    return updated


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a task."""
    task_repo = TaskRepository(db)
    meeting_repo = MeetingRepository(db)
    
    task = await task_repo.get_by_id(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    meeting = await meeting_repo.get_by_id(task.meeting_id)
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    await task_repo.delete(task_id)


@router.post("/bulk-action")
async def bulk_task_action(
    action_data: TaskBulkAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Perform bulk action on multiple tasks."""
    task_repo = TaskRepository(db)
    
    if action_data.action == "approve":
        count = await task_repo.bulk_update_status(
            action_data.task_ids,
            TaskStatus.PENDING,
        )
    elif action_data.action == "reject":
        count = await task_repo.bulk_update_status(
            action_data.task_ids,
            TaskStatus.REJECTED,
        )
    elif action_data.action == "delete":
        count = 0
        for task_id in action_data.task_ids:
            if await task_repo.delete(task_id):
                count += 1
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action: {action_data.action}",
        )
    
    return {"success": True, "affected_count": count}


@router.post("/sync", response_model=List[TaskSyncResult])
async def sync_tasks(
    sync_request: TaskSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TaskSyncResult]:
    """Sync tasks to external project management tool."""
    integration_repo = IntegrationRepository(db)
    
    # Verify integration access
    integration = await integration_repo.get_by_id(sync_request.integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    if not integration.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not active",
        )
    
    # Queue sync tasks
    results = []
    for task_id in sync_request.task_ids:
        # Start async sync
        celery_task = sync_task_to_external.delay(
            task_id=task_id,
            integration_id=sync_request.integration_id,
        )
        
        results.append(TaskSyncResult(
            task_id=task_id,
            success=True,  # Queued successfully
            external_id=None,  # Will be set after processing
            external_url=None,
            error=None,
        ))
    
    logger.info(
        "Tasks queued for sync",
        task_count=len(sync_request.task_ids),
        integration_id=sync_request.integration_id,
    )
    
    return results
