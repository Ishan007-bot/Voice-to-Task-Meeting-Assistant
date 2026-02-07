"""Meeting Endpoints"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import FileValidationError, NotFoundError
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.meeting import Meeting, MeetingStatus
from app.models.user import User
from app.repositories.meeting import MeetingRepository
from app.repositories.task import TaskRepository
from app.schemas.meeting import (
    MeetingCreate,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdate,
    MeetingUploadResponse,
)
from app.services.audio import AudioService
from app.workers.tasks import process_meeting

logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=MeetingListResponse)
async def list_meetings(
    page: int = 1,
    page_size: int = 20,
    status: Optional[MeetingStatus] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingListResponse:
    """List all meetings for the current user."""
    meeting_repo = MeetingRepository(db)
    task_repo = TaskRepository(db)
    
    offset = (page - 1) * page_size
    
    meetings = await meeting_repo.get_user_meetings(
        user_id=current_user.id,
        skip=offset,
        limit=page_size,
        status=status,
    )
    
    total = await meeting_repo.count_user_meetings(
        user_id=current_user.id,
        status=status,
    )
    
    # Enrich with task counts
    items = []
    for meeting in meetings:
        task_count = await task_repo.count_meeting_tasks(meeting.id)
        response = MeetingResponse(
            **meeting.to_dict(),
            task_count=task_count,
            has_transcript=meeting.transcript is not None,
        )
        items.append(response)
    
    return MeetingListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    meeting_data: MeetingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Meeting:
    """Create a new meeting (without audio upload)."""
    meeting_repo = MeetingRepository(db)
    
    participants_json = None
    if meeting_data.participants:
        participants_json = json.dumps(meeting_data.participants)
    
    meeting = await meeting_repo.create({
        "user_id": current_user.id,
        "title": meeting_data.title,
        "description": meeting_data.description,
        "meeting_date": meeting_data.meeting_date,
        "participants": participants_json,
        "status": MeetingStatus.PENDING,
    })
    
    return meeting


@router.post("/{meeting_id}/upload", response_model=MeetingUploadResponse)
async def upload_audio(
    meeting_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingUploadResponse:
    """
    Upload audio file for a meeting and start processing.
    Supports streaming upload for large files.
    """
    meeting_repo = MeetingRepository(db)
    
    # Get meeting
    meeting = await meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    if meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Validate file
    audio_service = AudioService()
    try:
        audio_format = audio_service.validate_file(
            filename=file.filename,
            content_type=file.content_type,
            file_size=file.size or 0,
        )
    except FileValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    
    # Update status to uploading
    await meeting_repo.update_status(
        meeting_id,
        MeetingStatus.UPLOADING,
        "Uploading audio file...",
    )
    
    try:
        # Save file (streaming)
        file_path, file_size = await audio_service.save_upload(
            file=file.file,
            filename=file.filename,
            meeting_id=meeting_id,
        )
        
        # Get duration
        duration = audio_service.get_audio_duration(file_path)
        
        # Update meeting with file info
        await meeting_repo.set_audio_info(
            meeting_id=meeting_id,
            file_path=file_path,
            file_name=file.filename,
            file_size=file_size,
            duration=duration,
            audio_format=audio_format,
        )
        
        # Start async processing
        celery_task = process_meeting.delay(meeting_id)
        
        # Store task ID
        await meeting_repo.update(meeting_id, {"celery_task_id": celery_task.id})
        
        logger.info(
            "Audio uploaded, processing started",
            meeting_id=meeting_id,
            celery_task_id=celery_task.id,
        )
        
        return MeetingUploadResponse(
            meeting_id=meeting_id,
            message="Upload successful. Processing started.",
            celery_task_id=celery_task.id,
        )
        
    except Exception as e:
        logger.error("Upload failed", error=str(e))
        await meeting_repo.update_status(
            meeting_id,
            MeetingStatus.FAILED,
            error_message=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingResponse:
    """Get meeting details by ID."""
    meeting_repo = MeetingRepository(db)
    task_repo = TaskRepository(db)
    
    meeting = await meeting_repo.get_by_id_with_relations(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    if meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    task_count = await task_repo.count_meeting_tasks(meeting_id)
    
    return MeetingResponse(
        **meeting.to_dict(),
        task_count=task_count,
        has_transcript=meeting.transcript is not None,
    )


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: str,
    meeting_update: MeetingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Meeting:
    """Update meeting details."""
    meeting_repo = MeetingRepository(db)
    
    meeting = await meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    if meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    update_data = meeting_update.model_dump(exclude_unset=True)
    if "participants" in update_data and update_data["participants"]:
        update_data["participants"] = json.dumps(update_data["participants"])
    
    updated = await meeting_repo.update(meeting_id, update_data)
    return updated


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a meeting and all associated data."""
    meeting_repo = MeetingRepository(db)
    
    meeting = await meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    if meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Cleanup audio files
    if meeting.audio_file_path:
        audio_service = AudioService()
        audio_service.cleanup_files(meeting.audio_file_path)
    
    await meeting_repo.delete(meeting_id)


@router.get("/{meeting_id}/status")
async def get_meeting_status(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get processing status for a meeting (for polling)."""
    meeting_repo = MeetingRepository(db)
    
    meeting = await meeting_repo.get_by_id(meeting_id)
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    if meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return {
        "meeting_id": meeting_id,
        "status": meeting.status.value,
        "status_message": meeting.status_message,
        "progress": meeting.processing_progress,
        "error_message": meeting.error_message,
    }
