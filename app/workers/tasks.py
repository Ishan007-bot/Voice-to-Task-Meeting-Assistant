"""
Celery Tasks for Background Processing
Handles audio transcription, task extraction, and sync operations.
"""

import asyncio
from typing import Optional

from celery import current_task

from app.core.logging import get_logger
from app.db.session import async_session_maker
from app.models.meeting import MeetingStatus
from app.models.task import TaskStatus
from app.repositories.meeting import MeetingRepository
from app.repositories.task import TaskRepository
from app.repositories.transcript import TranscriptRepository
from app.repositories.integration import IntegrationRepository
from app.services.audio import AudioService
from app.services.transcription import TranscriptionService
from app.services.task_extraction import TaskExtractionService
from app.services.deduplication import DeduplicationService
from app.services.pii_redaction import PIIRedactionService
from app.services.embedding import EmbeddingService
from app.integrations.factory import IntegrationFactory
from app.integrations.base import TaskPayload
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def run_async(coro):
    """Helper to run async code in Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, queue="transcription", max_retries=3)
def process_meeting(self, meeting_id: str) -> dict:
    """
    Main pipeline: Process meeting audio through transcription and extraction.
    
    Pipeline:
    1. Validate and preprocess audio
    2. Transcribe audio
    3. Redact PII
    4. Extract tasks
    5. Deduplicate tasks
    6. Store results
    """
    return run_async(_process_meeting_async(self, meeting_id))


async def _process_meeting_async(task, meeting_id: str) -> dict:
    """Async implementation of meeting processing."""
    
    async with async_session_maker() as session:
        meeting_repo = MeetingRepository(session)
        transcript_repo = TranscriptRepository(session)
        task_repo = TaskRepository(session)
        
        # Get meeting
        meeting = await meeting_repo.get_by_id(meeting_id)
        if not meeting:
            logger.error("Meeting not found", meeting_id=meeting_id)
            return {"error": "Meeting not found"}
        
        try:
            # Update status: Processing
            await meeting_repo.update_status(
                meeting_id,
                MeetingStatus.PROCESSING,
                "Preparing audio file...",
                progress=5,
            )
            await session.commit()
            
            # 1. Audio preprocessing
            audio_service = AudioService()
            normalized_path = audio_service.normalize_audio(meeting.audio_file_path)
            
            # Update status: Transcribing
            await meeting_repo.update_status(
                meeting_id,
                MeetingStatus.TRANSCRIBING,
                "Transcribing audio...",
                progress=20,
            )
            await session.commit()
            
            # 2. Transcription
            transcription_service = TranscriptionService()
            transcription_result = await transcription_service.transcribe(
                normalized_path,
                language="en",
            )
            
            # 3. PII Redaction
            await meeting_repo.update_status(
                meeting_id,
                MeetingStatus.PROCESSING,
                "Redacting sensitive information...",
                progress=50,
            )
            await session.commit()
            
            pii_service = PIIRedactionService()
            redacted_text, original_hash = await pii_service.redact_transcript(
                transcription_result["full_text"]
            )
            
            # Store transcript
            transcript = await transcript_repo.create_with_segments(
                transcript_data={
                    "meeting_id": meeting_id,
                    "full_text": redacted_text,
                    "language": transcription_result.get("language", "en"),
                    "word_count": len(redacted_text.split()),
                    "is_redacted": original_hash != "",
                    "original_text_hash": original_hash,
                },
                segments_data=transcription_result.get("segments", []),
            )
            
            # Generate transcript embedding
            embedding_service = EmbeddingService()
            transcript_embedding = await embedding_service.get_embedding(redacted_text)
            await transcript_repo.update_embedding(transcript.id, transcript_embedding)
            
            # 4. Task Extraction
            await meeting_repo.update_status(
                meeting_id,
                MeetingStatus.EXTRACTING,
                "Extracting action items...",
                progress=70,
            )
            await session.commit()
            
            extraction_service = TaskExtractionService()
            extracted_tasks = await extraction_service.extract_tasks(redacted_text)
            
            # 5. Create and deduplicate tasks
            await meeting_repo.update_status(
                meeting_id,
                MeetingStatus.PROCESSING,
                "Processing extracted tasks...",
                progress=85,
            )
            await session.commit()
            
            created_tasks = []
            for ext_task in extracted_tasks:
                task_data = {
                    "meeting_id": meeting_id,
                    "title": ext_task.title,
                    "description": ext_task.description,
                    "assignee": ext_task.assignee if ext_task.assignee != "Unassigned" else None,
                    "priority": extraction_service.map_priority_to_enum(ext_task.priority),
                    "due_date": extraction_service.parse_due_date(ext_task.due_date),
                    "due_date_text": ext_task.due_date if ext_task.due_date != "TBD" else None,
                    "status": TaskStatus.DRAFT,
                }
                created_task = await task_repo.create(task_data)
                created_tasks.append(created_task)
            
            # Generate embeddings and check for duplicates
            dedup_service = DeduplicationService(session)
            await dedup_service.bulk_generate_embeddings(created_tasks)
            await dedup_service.deduplicate_tasks(created_tasks, meeting.user_id)
            
            # 6. Finalize
            await meeting_repo.update_status(
                meeting_id,
                MeetingStatus.COMPLETED,
                "Processing complete!",
                progress=100,
            )
            await session.commit()
            
            # Cleanup temp files
            if normalized_path != meeting.audio_file_path:
                audio_service.cleanup_files(normalized_path)
            
            logger.info(
                "Meeting processing completed",
                meeting_id=meeting_id,
                tasks_extracted=len(created_tasks),
            )
            
            return {
                "meeting_id": meeting_id,
                "status": "completed",
                "transcript_id": transcript.id,
                "tasks_count": len(created_tasks),
            }
            
        except Exception as e:
            logger.error(
                "Meeting processing failed",
                meeting_id=meeting_id,
                error=str(e),
            )
            
            await meeting_repo.update_status(
                meeting_id,
                MeetingStatus.FAILED,
                error_message=str(e),
            )
            await session.commit()
            
            # Retry with exponential backoff
            raise task.retry(exc=e, countdown=60 * (2 ** task.request.retries))


@celery_app.task(bind=True, queue="sync", max_retries=3)
def sync_task_to_external(
    self,
    task_id: str,
    integration_id: str,
) -> dict:
    """Sync a task to an external project management tool."""
    return run_async(_sync_task_async(self, task_id, integration_id))


async def _sync_task_async(celery_task, task_id: str, integration_id: str) -> dict:
    """Async implementation of task sync."""
    
    async with async_session_maker() as session:
        task_repo = TaskRepository(session)
        integration_repo = IntegrationRepository(session)
        
        # Get task and integration
        task = await task_repo.get_by_id(task_id)
        integration = await integration_repo.get_by_id(integration_id)
        
        if not task or not integration:
            return {"error": "Task or integration not found"}
        
        try:
            # Create adapter
            adapter = IntegrationFactory.create(integration)
            
            # Build payload
            payload = TaskPayload.from_task(task)
            
            # Sync to external service
            result = await adapter.create_task(payload)
            
            if result.success:
                # Update task with external info
                await task_repo.update_sync_info(
                    task_id=task_id,
                    external_id=result.external_id,
                    external_service=adapter.service_name,
                    external_url=result.external_url,
                )
                
                # Update integration sync timestamp
                await integration_repo.update_sync_timestamp(integration_id)
                await integration_repo.clear_error(integration_id)
                
                await session.commit()
                
                logger.info(
                    "Task synced successfully",
                    task_id=task_id,
                    external_id=result.external_id,
                )
                
                return {
                    "success": True,
                    "external_id": result.external_id,
                    "external_url": result.external_url,
                }
            else:
                await integration_repo.record_error(integration_id, result.error)
                await session.commit()
                
                raise Exception(result.error)
                
        except Exception as e:
            logger.error("Task sync failed", task_id=task_id, error=str(e))
            raise celery_task.retry(exc=e, countdown=60 * (2 ** celery_task.request.retries))


@celery_app.task(queue="default")
def retry_failed_syncs() -> dict:
    """Periodic task to retry failed sync operations."""
    return run_async(_retry_failed_syncs_async())


async def _retry_failed_syncs_async() -> dict:
    """Retry syncs for tasks that failed previously."""
    async with async_session_maker() as session:
        task_repo = TaskRepository(session)
        
        # Get tasks that should be synced but aren't
        # (This would need additional logic based on your requirements)
        
        return {"retried": 0}


@celery_app.task(queue="default")
def cleanup_old_files() -> dict:
    """Periodic task to cleanup old audio files."""
    import os
    import time
    from pathlib import Path
    
    from app.core.config import settings
    
    upload_dir = Path(settings.upload_dir)
    if not upload_dir.exists():
        return {"cleaned": 0}
    
    # Files older than 30 days
    max_age = 30 * 24 * 60 * 60
    now = time.time()
    cleaned = 0
    
    for meeting_dir in upload_dir.iterdir():
        if meeting_dir.is_dir():
            for file in meeting_dir.iterdir():
                if now - file.stat().st_mtime > max_age:
                    try:
                        file.unlink()
                        cleaned += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete {file}: {e}")
    
    logger.info(f"Cleaned up {cleaned} old files")
    return {"cleaned": cleaned}
