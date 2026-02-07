"""
Custom Exception Classes
Centralized exception handling for the application.
"""

from typing import Any, Dict, Optional


class VoiceToTaskException(Exception):
    """Base exception for Voice-to-Task application."""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AudioProcessingError(VoiceToTaskException):
    """Raised when audio processing fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="AUDIO_PROCESSING_ERROR",
            status_code=422,
            details=details,
        )


class TranscriptionError(VoiceToTaskException):
    """Raised when transcription fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="TRANSCRIPTION_ERROR",
            status_code=500,
            details=details,
        )


class TaskExtractionError(VoiceToTaskException):
    """Raised when task extraction fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="TASK_EXTRACTION_ERROR",
            status_code=500,
            details=details,
        )


class FileValidationError(VoiceToTaskException):
    """Raised when file validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="FILE_VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class IntegrationError(VoiceToTaskException):
    """Raised when external integration fails."""
    
    def __init__(
        self,
        message: str,
        provider: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code=f"{provider.upper()}_INTEGRATION_ERROR",
            status_code=502,
            details=details,
        )


class AuthenticationError(VoiceToTaskException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
        )


class AuthorizationError(VoiceToTaskException):
    """Raised when authorization fails."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
        )


class NotFoundError(VoiceToTaskException):
    """Raised when a resource is not found."""
    
    def __init__(self, resource: str, resource_id: Any):
        super().__init__(
            message=f"{resource} with ID '{resource_id}' not found",
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "id": str(resource_id)},
        )


class DuplicateError(VoiceToTaskException):
    """Raised when a duplicate resource is detected."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DUPLICATE_ERROR",
            status_code=409,
            details=details,
        )


class RateLimitError(VoiceToTaskException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )
