"""Meeting Pydantic Schemas"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.meeting import MeetingStatus


class MeetingCreate(BaseModel):
    """Meeting creation schema."""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None
    participants: Optional[List[str]] = None


class MeetingUpdate(BaseModel):
    """Meeting update schema."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None
    participants: Optional[List[str]] = None


class MeetingStatusUpdate(BaseModel):
    """Meeting status update (internal use)."""
    status: MeetingStatus
    status_message: Optional[str] = None
    processing_progress: Optional[int] = Field(None, ge=0, le=100)
    error_message: Optional[str] = None


class MeetingResponse(BaseModel):
    """Meeting response schema."""
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    audio_file_name: Optional[str] = None
    audio_file_size: Optional[int] = None
    audio_duration_seconds: Optional[int] = None
    audio_format: Optional[str] = None
    status: MeetingStatus
    status_message: Optional[str] = None
    processing_progress: int = 0
    meeting_date: Optional[datetime] = None
    participants: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Counts for related items
    task_count: int = 0
    has_transcript: bool = False

    model_config = {"from_attributes": True}


class MeetingListResponse(BaseModel):
    """Meeting list response with pagination."""
    items: List[MeetingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MeetingUploadResponse(BaseModel):
    """Response after audio upload."""
    meeting_id: str
    message: str
    celery_task_id: Optional[str] = None
