"""Transcript Repository"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transcript import Transcript, TranscriptSegment
from app.repositories.base import BaseRepository


class TranscriptRepository(BaseRepository[Transcript]):
    """Repository for Transcript operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Transcript, session)
    
    async def get_by_meeting_id(self, meeting_id: str) -> Optional[Transcript]:
        """Get transcript for a specific meeting."""
        result = await self.session.execute(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()
    
    async def create_with_segments(
        self,
        transcript_data: dict,
        segments_data: List[dict],
    ) -> Transcript:
        """Create transcript with its segments."""
        transcript = Transcript(**transcript_data)
        self.session.add(transcript)
        await self.session.flush()
        
        for seq, segment_data in enumerate(segments_data):
            segment = TranscriptSegment(
                transcript_id=transcript.id,
                sequence_number=seq,
                **segment_data,
            )
            self.session.add(segment)
        
        await self.session.flush()
        await self.session.refresh(transcript)
        return transcript
    
    async def update_segment_speaker(
        self,
        segment_id: str,
        speaker_name: str,
    ) -> Optional[TranscriptSegment]:
        """Update speaker name for a segment."""
        result = await self.session.execute(
            select(TranscriptSegment).where(TranscriptSegment.id == segment_id)
        )
        segment = result.scalar_one_or_none()
        
        if segment:
            segment.speaker_name = speaker_name
            await self.session.flush()
            await self.session.refresh(segment)
        
        return segment
    
    async def bulk_update_speaker_names(
        self,
        transcript_id: str,
        speaker_mappings: dict[str, str],  # label -> name
    ) -> int:
        """Bulk update speaker names based on label mappings."""
        result = await self.session.execute(
            select(TranscriptSegment).where(
                TranscriptSegment.transcript_id == transcript_id
            )
        )
        segments = result.scalars().all()
        
        updated_count = 0
        for segment in segments:
            if segment.speaker_label in speaker_mappings:
                segment.speaker_name = speaker_mappings[segment.speaker_label]
                updated_count += 1
        
        await self.session.flush()
        return updated_count
    
    async def set_redacted(
        self,
        transcript_id: str,
        redacted_text: str,
        original_hash: str,
    ) -> Optional[Transcript]:
        """Mark transcript as redacted and update text."""
        return await self.update(
            transcript_id,
            {
                "full_text": redacted_text,
                "is_redacted": True,
                "original_text_hash": original_hash,
            }
        )
    
    async def update_embedding(
        self,
        transcript_id: str,
        embedding: List[float],
    ) -> Optional[Transcript]:
        """Update transcript embedding for semantic search."""
        return await self.update(transcript_id, {"embedding": embedding})
