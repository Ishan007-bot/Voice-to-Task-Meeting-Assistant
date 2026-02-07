"""
Transcription Service
High-fidelity speech-to-text using OpenAI Whisper with chunking and diarization.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

import whisper
from openai import OpenAI

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.core.logging import get_logger
from app.services.audio import AudioService

logger = get_logger(__name__)


class TranscriptionService:
    """
    Service for audio transcription using OpenAI Whisper.
    Supports both local and API-based transcription.
    """
    
    def __init__(self):
        self.model_name = settings.whisper_model
        self.use_api = self.model_name.lower() == "api"
        self.enable_diarization = settings.enable_diarization
        self._local_model = None
        self._openai_client = None
        self.audio_service = AudioService()
    
    @property
    def local_model(self):
        """Lazy load the local Whisper model."""
        if self._local_model is None and not self.use_api:
            logger.info("Loading Whisper model", model=self.model_name)
            self._local_model = whisper.load_model(self.model_name)
        return self._local_model
    
    @property
    def openai_client(self):
        """Lazy load the OpenAI client."""
        if self._openai_client is None:
            self._openai_client = OpenAI(api_key=settings.openai_api_key)
        return self._openai_client
    
    async def transcribe(
        self,
        audio_path: str,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Transcribe audio file.
        Returns dict with full_text, segments, and metadata.
        """
        try:
            # Get audio duration
            duration = self.audio_service.get_audio_duration(audio_path)
            
            # Normalize audio for consistent processing
            normalized_path = self.audio_service.normalize_audio(audio_path)
            
            # Check if we need chunked processing (for long meetings)
            if duration > settings.audio_chunk_duration_seconds:
                result = await self._transcribe_chunked(normalized_path, language)
            else:
                result = await self._transcribe_single(normalized_path, language)
            
            # Add diarization if enabled
            if self.enable_diarization:
                result = await self._add_diarization(normalized_path, result)
            
            # Cleanup normalized file
            if normalized_path != audio_path:
                self.audio_service.cleanup_files(normalized_path)
            
            logger.info(
                "Transcription completed",
                duration=duration,
                segments=len(result.get("segments", [])),
            )
            
            return result
            
        except Exception as e:
            logger.error("Transcription failed", error=str(e))
            raise TranscriptionError(f"Transcription failed: {str(e)}")
    
    async def _transcribe_single(
        self,
        audio_path: str,
        language: str,
    ) -> Dict[str, Any]:
        """Transcribe a single audio file."""
        if self.use_api:
            return await self._transcribe_api(audio_path, language)
        else:
            return await self._transcribe_local(audio_path, language)
    
    async def _transcribe_local(
        self,
        audio_path: str,
        language: str,
    ) -> Dict[str, Any]:
        """Transcribe using local Whisper model."""
        try:
            result = self.local_model.transcribe(
                audio_path,
                language=language,
                verbose=False,
                word_timestamps=True,
            )
            
            segments = []
            for seg in result.get("segments", []):
                segments.append({
                    "text": seg["text"].strip(),
                    "start_time": seg["start"],
                    "end_time": seg["end"],
                    "confidence": seg.get("avg_logprob", 0),
                })
            
            return {
                "full_text": result["text"].strip(),
                "language": result.get("language", language),
                "segments": segments,
            }
            
        except Exception as e:
            raise TranscriptionError(f"Local transcription failed: {str(e)}")
    
    async def _transcribe_api(
        self,
        audio_path: str,
        language: str,
    ) -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper API."""
        try:
            with open(audio_path, "rb") as audio_file:
                response = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )
            
            segments = []
            for seg in response.segments or []:
                segments.append({
                    "text": seg.text.strip(),
                    "start_time": seg.start,
                    "end_time": seg.end,
                    "confidence": None,  # API doesn't provide this
                })
            
            return {
                "full_text": response.text.strip(),
                "language": response.language or language,
                "segments": segments,
            }
            
        except Exception as e:
            raise TranscriptionError(f"API transcription failed: {str(e)}")
    
    async def _transcribe_chunked(
        self,
        audio_path: str,
        language: str,
    ) -> Dict[str, Any]:
        """
        Transcribe long audio by splitting into chunks.
        Handles meetings over 20 minutes to prevent memory issues.
        """
        try:
            chunks = self.audio_service.split_audio_into_chunks(audio_path)
            
            all_segments = []
            full_text_parts = []
            time_offset = 0.0
            
            for i, chunk_path in enumerate(chunks):
                logger.info(f"Transcribing chunk {i+1}/{len(chunks)}")
                
                result = await self._transcribe_single(chunk_path, language)
                
                # Adjust timestamps for chunk offset
                for seg in result.get("segments", []):
                    seg["start_time"] += time_offset
                    seg["end_time"] += time_offset
                    all_segments.append(seg)
                
                full_text_parts.append(result["full_text"])
                
                # Update offset for next chunk
                if result.get("segments"):
                    time_offset = result["segments"][-1]["end_time"]
                else:
                    # Estimate based on chunk duration
                    chunk_duration = self.audio_service.get_audio_duration(chunk_path)
                    time_offset += chunk_duration
                
                # Cleanup chunk file
                self.audio_service.cleanup_files(chunk_path)
            
            return {
                "full_text": " ".join(full_text_parts),
                "language": language,
                "segments": all_segments,
            }
            
        except Exception as e:
            raise TranscriptionError(f"Chunked transcription failed: {str(e)}")
    
    async def _add_diarization(
        self,
        audio_path: str,
        transcription_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add speaker diarization to transcription segments.
        Uses pyannote.audio for speaker detection.
        """
        try:
            from pyannote.audio import Pipeline
            
            # Check for HuggingFace token
            hf_token = settings.hf_auth_token
            if not hf_token:
                logger.warning("HuggingFace token not set, skipping diarization")
                return transcription_result
            
            # Load diarization pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token,
            )
            
            # Run diarization
            diarization = pipeline(audio_path)
            
            # Build speaker timeline
            speaker_timeline = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speaker_timeline.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker,
                })
            
            # Assign speakers to segments
            for segment in transcription_result.get("segments", []):
                speaker = self._find_speaker_for_segment(
                    segment["start_time"],
                    segment["end_time"],
                    speaker_timeline,
                )
                segment["speaker_label"] = speaker
            
            logger.info(
                "Diarization completed",
                speakers=len(set(t["speaker"] for t in speaker_timeline)),
            )
            
            return transcription_result
            
        except ImportError:
            logger.warning("pyannote.audio not installed, skipping diarization")
            return transcription_result
        except Exception as e:
            logger.warning("Diarization failed, continuing without it", error=str(e))
            return transcription_result
    
    def _find_speaker_for_segment(
        self,
        start_time: float,
        end_time: float,
        speaker_timeline: List[Dict],
    ) -> Optional[str]:
        """Find the dominant speaker for a segment based on overlap."""
        max_overlap = 0.0
        assigned_speaker = None
        
        for turn in speaker_timeline:
            # Calculate overlap
            overlap_start = max(start_time, turn["start"])
            overlap_end = min(end_time, turn["end"])
            overlap = max(0, overlap_end - overlap_start)
            
            if overlap > max_overlap:
                max_overlap = overlap
                assigned_speaker = turn["speaker"]
        
        return assigned_speaker
