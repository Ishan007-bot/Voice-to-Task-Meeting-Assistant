"""Meeting Repository"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting import Meeting, MeetingStatus
from app.repositories.base import BaseRepository


class MeetingRepository(BaseRepository[Meeting]):
    """Repository for Meeting operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Meeting, session)
    
    async def get_by_id_with_relations(self, meeting_id: str) -> Optional[Meeting]:
        """Get meeting with transcript and tasks loaded."""
        result = await self.session.execute(
            select(Meeting)
            .options(
                selectinload(Meeting.transcript),
                selectinload(Meeting.tasks),
            )
            .where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_meetings(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        status: Optional[MeetingStatus] = None,
    ) -> List[Meeting]:
        """Get meetings for a specific user."""
        query = select(Meeting).where(Meeting.user_id == user_id)
        
        if status:
            query = query.where(Meeting.status == status)
        
        query = query.order_by(Meeting.created_at.desc())
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def count_user_meetings(
        self,
        user_id: str,
        status: Optional[MeetingStatus] = None,
    ) -> int:
        """Count meetings for a user."""
        query = select(func.count()).select_from(Meeting).where(
            Meeting.user_id == user_id
        )
        
        if status:
            query = query.where(Meeting.status == status)
        
        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def update_status(
        self,
        meeting_id: str,
        status: MeetingStatus,
        status_message: Optional[str] = None,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Meeting]:
        """Update meeting processing status."""
        update_data = {"status": status}
        
        if status_message is not None:
            update_data["status_message"] = status_message
        if progress is not None:
            update_data["processing_progress"] = progress
        if error_message is not None:
            update_data["error_message"] = error_message
        
        return await self.update(meeting_id, update_data)
    
    async def set_audio_info(
        self,
        meeting_id: str,
        file_path: str,
        file_name: str,
        file_size: int,
        duration: Optional[int] = None,
        audio_format: Optional[str] = None,
    ) -> Optional[Meeting]:
        """Set audio file information."""
        return await self.update(
            meeting_id,
            {
                "audio_file_path": file_path,
                "audio_file_name": file_name,
                "audio_file_size": file_size,
                "audio_duration_seconds": duration,
                "audio_format": audio_format,
            }
        )
    
    async def get_pending_meetings(self, limit: int = 10) -> List[Meeting]:
        """Get meetings pending processing."""
        result = await self.session.execute(
            select(Meeting)
            .where(Meeting.status == MeetingStatus.PENDING)
            .order_by(Meeting.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
