"""Pydantic Schemas for API validation and serialization."""

from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    TokenResponse,
    TokenRefresh,
)
from app.schemas.meeting import (
    MeetingCreate,
    MeetingUpdate,
    MeetingResponse,
    MeetingListResponse,
    MeetingStatusUpdate,
)
from app.schemas.transcript import (
    TranscriptResponse,
    TranscriptSegmentResponse,
)
from app.schemas.task import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
    TaskBulkAction,
    ExtractedTask,
    TaskExtractionResult,
)
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationListResponse,
)
from app.schemas.common import (
    HealthResponse,
    PaginationParams,
    PaginatedResponse,
    StatusMessage,
)

__all__ = [
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "TokenResponse",
    "TokenRefresh",
    # Meeting
    "MeetingCreate",
    "MeetingUpdate",
    "MeetingResponse",
    "MeetingListResponse",
    "MeetingStatusUpdate",
    # Transcript
    "TranscriptResponse",
    "TranscriptSegmentResponse",
    # Task
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "TaskListResponse",
    "TaskBulkAction",
    "ExtractedTask",
    "TaskExtractionResult",
    # Integration
    "IntegrationCreate",
    "IntegrationUpdate",
    "IntegrationResponse",
    "IntegrationListResponse",
    # Common
    "HealthResponse",
    "PaginationParams",
    "PaginatedResponse",
    "StatusMessage",
]
