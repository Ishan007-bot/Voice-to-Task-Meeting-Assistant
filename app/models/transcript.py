"""Transcript Models"""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.meeting import Meeting


class Transcript(Base):
    """Full transcript for a meeting."""
    
    __tablename__ = "transcripts"
    
    # Meeting relationship
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    
    # Full text
    full_text: Mapped[str] = mapped_column(Text)
    
    # Metadata
    language: Mapped[str] = mapped_column(String(10), default="en")
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # PII redaction tracking
    is_redacted: Mapped[bool] = mapped_column(default=False)
    original_text_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Embedding for semantic search (1536 dimensions for OpenAI embeddings)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536), nullable=True)
    
    # Relationships
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="transcript")
    segments: Mapped[List["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="transcript", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Transcript for Meeting {self.meeting_id}>"


class TranscriptSegment(Base):
    """Individual segment of a transcript with speaker diarization."""
    
    __tablename__ = "transcript_segments"
    
    # Transcript relationship
    transcript_id: Mapped[str] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Segment content
    text: Mapped[str] = mapped_column(Text)
    speaker_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    speaker_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Timing information
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    
    # Ordering
    sequence_number: Mapped[int] = mapped_column(Integer, index=True)
    
    # Confidence
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Segment embedding for semantic search
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536), nullable=True)
    
    # Relationships
    transcript: Mapped["Transcript"] = relationship(
        "Transcript", back_populates="segments"
    )
    
    def __repr__(self) -> str:
        return f"<TranscriptSegment {self.sequence_number}: {self.speaker_label}>"
