"""Task Model"""

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.meeting import Meeting


class TaskStatus(str, enum.Enum):
    """Task status enum."""
    DRAFT = "draft"  # Extracted but not reviewed
    PENDING = "pending"  # Reviewed and pending sync
    SYNCED = "synced"  # Synced to external service
    COMPLETED = "completed"  # Marked as done
    REJECTED = "rejected"  # User rejected this task
    FAILED = "failed"  # Sync failed


class TaskPriority(str, enum.Enum):
    """Task priority enum."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task(Base):
    """Extracted task from meeting transcript."""
    
    __tablename__ = "tasks"
    
    # Meeting relationship
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Task details
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Assignment
    assignee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assignee_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Priority and due date
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority),
        default=TaskPriority.MEDIUM,
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Original text like "next Friday"
    
    # Status tracking
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        default=TaskStatus.DRAFT,
        index=True,
    )
    
    # Source context
    source_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # The transcript segment that generated this task
    source_segment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # AI extraction metadata
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # External integration
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # ID in external system
    external_service: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # asana, trello, jira
    external_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # User modifications
    is_user_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    original_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Deduplication
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Embedding for semantic deduplication (1536 dimensions for OpenAI embeddings)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536), nullable=True)
    
    # Relationships
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="tasks")
    
    def __repr__(self) -> str:
        return f"<Task {self.title[:50]} ({self.status.value})>"
