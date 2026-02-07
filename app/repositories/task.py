"""Task Repository"""

from typing import List, Optional, Tuple

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskPriority, TaskStatus
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for Task operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)
    
    async def get_meeting_tasks(
        self,
        meeting_id: str,
        status: Optional[TaskStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Task]:
        """Get tasks for a specific meeting."""
        query = select(Task).where(Task.meeting_id == meeting_id)
        
        if status:
            query = query.where(Task.status == status)
        
        query = query.order_by(Task.created_at.asc())
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def count_meeting_tasks(
        self,
        meeting_id: str,
        status: Optional[TaskStatus] = None,
    ) -> int:
        """Count tasks for a meeting."""
        query = select(func.count()).select_from(Task).where(
            Task.meeting_id == meeting_id
        )
        
        if status:
            query = query.where(Task.status == status)
        
        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def bulk_create(self, tasks_data: List[dict]) -> List[Task]:
        """Create multiple tasks at once."""
        tasks = []
        for task_data in tasks_data:
            task = Task(**task_data)
            self.session.add(task)
            tasks.append(task)
        
        await self.session.flush()
        
        for task in tasks:
            await self.session.refresh(task)
        
        return tasks
    
    async def bulk_update_status(
        self,
        task_ids: List[str],
        status: TaskStatus,
    ) -> int:
        """Bulk update task status."""
        result = await self.session.execute(
            select(Task).where(Task.id.in_(task_ids))
        )
        tasks = result.scalars().all()
        
        for task in tasks:
            task.status = status
        
        await self.session.flush()
        return len(tasks)
    
    async def find_similar_tasks(
        self,
        embedding: List[float],
        user_id: str,
        threshold: float = 0.85,
        limit: int = 5,
    ) -> List[Tuple[Task, float]]:
        """Find similar tasks using vector similarity search."""
        # Use pgvector's cosine similarity
        # 1 - cosine_distance gives cosine similarity
        query = text("""
            SELECT t.*, 1 - (t.embedding <=> :embedding::vector) as similarity
            FROM tasks t
            JOIN meetings m ON t.meeting_id = m.id
            WHERE m.user_id = :user_id
            AND t.embedding IS NOT NULL
            AND 1 - (t.embedding <=> :embedding::vector) > :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """)
        
        result = await self.session.execute(
            query,
            {
                "embedding": str(embedding),
                "user_id": user_id,
                "threshold": threshold,
                "limit": limit,
            }
        )
        
        rows = result.fetchall()
        tasks_with_scores = []
        
        for row in rows:
            task = await self.get_by_id(row.id)
            if task:
                tasks_with_scores.append((task, row.similarity))
        
        return tasks_with_scores
    
    async def update_sync_info(
        self,
        task_id: str,
        external_id: str,
        external_service: str,
        external_url: Optional[str] = None,
    ) -> Optional[Task]:
        """Update task with external service sync info."""
        from datetime import datetime, timezone
        
        return await self.update(
            task_id,
            {
                "external_id": external_id,
                "external_service": external_service,
                "external_url": external_url,
                "synced_at": datetime.now(timezone.utc),
                "status": TaskStatus.SYNCED,
            }
        )
    
    async def mark_as_duplicate(
        self,
        task_id: str,
        duplicate_of_id: str,
        similarity_score: float,
    ) -> Optional[Task]:
        """Mark task as duplicate of another."""
        return await self.update(
            task_id,
            {
                "is_duplicate": True,
                "duplicate_of_id": duplicate_of_id,
                "similarity_score": similarity_score,
            }
        )
    
    async def get_user_tasks(
        self,
        user_id: str,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Task]:
        """Get all tasks for a user across all meetings."""
        from app.models.meeting import Meeting
        
        query = (
            select(Task)
            .join(Meeting)
            .where(Meeting.user_id == user_id)
        )
        
        if status:
            query = query.where(Task.status == status)
        if priority:
            query = query.where(Task.priority == priority)
        
        query = query.order_by(Task.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
