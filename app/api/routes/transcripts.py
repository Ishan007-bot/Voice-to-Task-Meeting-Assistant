"""Transcript Endpoints"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.meeting import MeetingRepository
from app.repositories.transcript import TranscriptRepository
from app.schemas.transcript import (
    TranscriptResponse,
    TranscriptSegmentResponse,
    TranscriptUpdateSpeakers,
)

router = APIRouter()


@router.get("/meeting/{meeting_id}", response_model=TranscriptResponse)
async def get_meeting_transcript(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptResponse:
    """Get transcript for a specific meeting."""
    meeting_repo = MeetingRepository(db)
    transcript_repo = TranscriptRepository(db)
    
    # Verify meeting access
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
    
    transcript = await transcript_repo.get_by_meeting_id(meeting_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found. Processing may still be in progress.",
        )
    
    segments = [
        TranscriptSegmentResponse(
            id=seg.id,
            text=seg.text,
            speaker_label=seg.speaker_label,
            speaker_name=seg.speaker_name,
            start_time=seg.start_time,
            end_time=seg.end_time,
            sequence_number=seg.sequence_number,
            confidence=seg.confidence,
        )
        for seg in sorted(transcript.segments, key=lambda s: s.sequence_number)
    ]
    
    return TranscriptResponse(
        id=transcript.id,
        meeting_id=transcript.meeting_id,
        full_text=transcript.full_text,
        language=transcript.language,
        confidence_score=transcript.confidence_score,
        word_count=transcript.word_count,
        is_redacted=transcript.is_redacted,
        segments=segments,
        created_at=transcript.created_at,
        updated_at=transcript.updated_at,
    )


@router.patch("/meeting/{meeting_id}/speakers")
async def update_speaker_names(
    meeting_id: str,
    speaker_data: TranscriptUpdateSpeakers,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Update speaker names in transcript.
    Maps speaker labels (e.g., "SPEAKER_00") to actual names.
    """
    meeting_repo = MeetingRepository(db)
    transcript_repo = TranscriptRepository(db)
    
    # Verify meeting access
    meeting = await meeting_repo.get_by_id(meeting_id)
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    transcript = await transcript_repo.get_by_meeting_id(meeting_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )
    
    # Build mapping
    speaker_mappings = {
        m.speaker_label: m.speaker_name
        for m in speaker_data.speaker_mappings
    }
    
    updated_count = await transcript_repo.bulk_update_speaker_names(
        transcript.id,
        speaker_mappings,
    )
    
    return {
        "success": True,
        "updated_segments": updated_count,
    }


@router.get("/meeting/{meeting_id}/speakers")
async def get_speakers(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get unique speaker labels from transcript."""
    meeting_repo = MeetingRepository(db)
    transcript_repo = TranscriptRepository(db)
    
    meeting = await meeting_repo.get_by_id(meeting_id)
    if not meeting or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    
    transcript = await transcript_repo.get_by_meeting_id(meeting_id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )
    
    # Get unique speakers
    speakers = {}
    for segment in transcript.segments:
        if segment.speaker_label and segment.speaker_label not in speakers:
            speakers[segment.speaker_label] = segment.speaker_name
    
    return {
        "speakers": [
            {"label": label, "name": name}
            for label, name in speakers.items()
        ]
    }
