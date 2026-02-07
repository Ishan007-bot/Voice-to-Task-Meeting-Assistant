"""Transcript Pydantic Schemas"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TranscriptSegmentResponse(BaseModel):
    """Transcript segment response."""
    id: str
    text: str
    speaker_label: Optional[str] = None
    speaker_name: Optional[str] = None
    start_time: float
    end_time: float
    sequence_number: int
    confidence: Optional[float] = None

    model_config = {"from_attributes": True}


class TranscriptResponse(BaseModel):
    """Full transcript response."""
    id: str
    meeting_id: str
    full_text: str
    language: str
    confidence_score: Optional[float] = None
    word_count: Optional[int] = None
    is_redacted: bool
    segments: List[TranscriptSegmentResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TranscriptSummary(BaseModel):
    """Transcript summary (without segments)."""
    id: str
    meeting_id: str
    language: str
    word_count: Optional[int] = None
    is_redacted: bool
    created_at: datetime


class SpeakerMapping(BaseModel):
    """Map speaker labels to names."""
    speaker_label: str
    speaker_name: str


class TranscriptUpdateSpeakers(BaseModel):
    """Update speaker names in transcript."""
    speaker_mappings: List[SpeakerMapping]
