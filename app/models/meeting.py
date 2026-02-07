"""Meeting Model"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.transcript import Transcript
    from app.models.task import Task


class MeetingStatus(str, enum.Enum):
    """Meeting processing status."""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


class Meeting(Base):
    """Meeting/Recording model."""
    
    __tablename__ = "meetings"
    
    # User relationship
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Meeting info
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Audio file information
    audio_file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    audio_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    audio_file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    audio_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    audio_format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Processing status
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus),
        default=MeetingStatus.PENDING,
        index=True,
    )
    status_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_progress: Mapped[int] = mapped_column(Integer, default=0)
    
    # Celery task tracking
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Meeting metadata
    meeting_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    participants: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="meetings")
    transcript: Mapped[Optional["Transcript"]] = relationship(
        "Transcript", back_populates="meeting", uselist=False, cascade="all, delete-orphan"
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task", back_populates="meeting", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Meeting {self.title} ({self.status.value})>"
