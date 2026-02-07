"""
Audio Processing Service
Handles audio file validation, preprocessing, and format conversion.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import BinaryIO, Optional, Tuple

from pydub import AudioSegment

from app.core.config import settings
from app.core.exceptions import AudioProcessingError, FileValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)


class AudioService:
    """Service for audio file processing and validation."""
    
    MIME_TYPE_MAP = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/wave": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "audio/x-flac": "flac",
        "audio/webm": "webm",
    }
    
    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.allowed_formats = settings.allowed_audio_formats_list
        self.max_size = settings.max_upload_size_bytes
        self.sample_rate = settings.audio_sample_rate
    
    def validate_file(
        self,
        filename: str,
        content_type: Optional[str],
        file_size: int,
    ) -> str:
        """
        Validate uploaded audio file.
        Returns the detected audio format.
        """
        # Check file size
        if file_size > self.max_size:
            raise FileValidationError(
                f"File size {file_size / (1024*1024):.1f}MB exceeds limit of {settings.max_upload_size_mb}MB",
                details={"max_size_mb": settings.max_upload_size_mb},
            )
        
        # Get file extension
        ext = Path(filename).suffix.lower().lstrip(".")
        
        # Check extension
        if ext not in self.allowed_formats:
            raise FileValidationError(
                f"File format '{ext}' is not supported",
                details={"allowed_formats": self.allowed_formats},
            )
        
        # Validate MIME type if provided
        if content_type:
            detected_format = self.MIME_TYPE_MAP.get(content_type)
            if detected_format and detected_format != ext:
                logger.warning(
                    "MIME type mismatch",
                    extension=ext,
                    content_type=content_type,
                    detected=detected_format,
                )
        
        return ext
    
    async def save_upload(
        self,
        file: BinaryIO,
        filename: str,
        meeting_id: str,
    ) -> Tuple[str, int]:
        """
        Save uploaded file to disk.
        Returns (file_path, file_size).
        """
        try:
            # Create meeting-specific directory
            meeting_dir = self.upload_dir / meeting_id
            meeting_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate safe filename
            safe_filename = self._sanitize_filename(filename)
            file_path = meeting_dir / safe_filename
            
            # Stream write to file
            file_size = 0
            with open(file_path, "wb") as f:
                while chunk := file.read(8192):  # 8KB chunks
                    f.write(chunk)
                    file_size += len(chunk)
            
            logger.info(
                "Audio file saved",
                meeting_id=meeting_id,
                filename=safe_filename,
                size=file_size,
            )
            
            return str(file_path), file_size
            
        except Exception as e:
            logger.error("Failed to save audio file", error=str(e))
            raise AudioProcessingError(f"Failed to save file: {str(e)}")
    
    def get_audio_duration(self, file_path: str) -> int:
        """
        Get audio duration in seconds using ffprobe.
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    file_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                raise AudioProcessingError(f"ffprobe failed: {result.stderr}")
            
            duration = float(result.stdout.strip())
            return int(duration)
            
        except subprocess.TimeoutExpired:
            raise AudioProcessingError("Audio duration detection timed out")
        except ValueError:
            raise AudioProcessingError("Could not parse audio duration")
    
    def normalize_audio(self, input_path: str) -> str:
        """
        Normalize audio to standard format (16kHz mono WAV).
        Returns path to normalized file.
        """
        try:
            output_path = input_path.rsplit(".", 1)[0] + "_normalized.wav"
            
            # Use ffmpeg for conversion
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",  # Overwrite output
                    "-i", input_path,
                    "-ar", str(self.sample_rate),  # Sample rate
                    "-ac", "1",  # Mono
                    "-acodec", "pcm_s16le",  # 16-bit PCM
                    output_path,
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode != 0:
                raise AudioProcessingError(f"Audio normalization failed: {result.stderr}")
            
            logger.info("Audio normalized", input=input_path, output=output_path)
            return output_path
            
        except subprocess.TimeoutExpired:
            raise AudioProcessingError("Audio normalization timed out")
    
    def split_audio_into_chunks(
        self,
        file_path: str,
        chunk_duration_seconds: int = None,
    ) -> list[str]:
        """
        Split audio into chunks for processing long recordings.
        Returns list of chunk file paths.
        """
        chunk_duration = chunk_duration_seconds or settings.audio_chunk_duration_seconds
        
        try:
            audio = AudioSegment.from_file(file_path)
            duration_ms = len(audio)
            chunk_duration_ms = chunk_duration * 1000
            
            if duration_ms <= chunk_duration_ms:
                return [file_path]
            
            chunks = []
            chunk_dir = Path(file_path).parent / "chunks"
            chunk_dir.mkdir(exist_ok=True)
            
            for i, start_ms in enumerate(range(0, duration_ms, chunk_duration_ms)):
                end_ms = min(start_ms + chunk_duration_ms, duration_ms)
                chunk = audio[start_ms:end_ms]
                
                chunk_path = chunk_dir / f"chunk_{i:04d}.wav"
                chunk.export(str(chunk_path), format="wav")
                chunks.append(str(chunk_path))
            
            logger.info(
                "Audio split into chunks",
                file=file_path,
                chunk_count=len(chunks),
                chunk_duration_seconds=chunk_duration,
            )
            
            return chunks
            
        except Exception as e:
            logger.error("Failed to split audio", error=str(e))
            raise AudioProcessingError(f"Failed to split audio: {str(e)}")
    
    def cleanup_files(self, *file_paths: str) -> None:
        """Clean up temporary files."""
        for path in file_paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning("Failed to cleanup file", path=path, error=str(e))
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
        import re
        import uuid
        
        # Get extension
        ext = Path(filename).suffix.lower()
        
        # Generate safe name
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(filename).stem)
        safe_name = safe_name[:50]  # Limit length
        
        # Add unique suffix
        unique_suffix = str(uuid.uuid4())[:8]
        
        return f"{safe_name}_{unique_suffix}{ext}"
