"""Task Pydantic Schemas"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.task import TaskPriority, TaskStatus


class ExtractedTask(BaseModel):
    """Task extracted by LLM (structured output format)."""
    title: str = Field(..., description="Short descriptive title")
    description: Optional[str] = Field(None, description="Detailed context of the task")
    priority: str = Field(default="Medium", description="High/Medium/Low")
    assignee: str = Field(default="Unassigned", description="Name or 'Unassigned'")
    due_date: str = Field(default="TBD", description="ISO-8601 or 'TBD'")


class TaskExtractionResult(BaseModel):
    """Result from LLM task extraction."""
    tasks: List[ExtractedTask]


class TaskCreate(BaseModel):
    """Task creation schema."""
    meeting_id: str
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    assignee: Optional[str] = Field(None, max_length=255)
    assignee_email: Optional[str] = Field(None, max_length=255)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[date] = None
    due_date_text: Optional[str] = None
    source_text: Optional[str] = None


class TaskUpdate(BaseModel):
    """Task update schema."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    assignee: Optional[str] = Field(None, max_length=255)
    assignee_email: Optional[str] = Field(None, max_length=255)
    priority: Optional[TaskPriority] = None
    due_date: Optional[date] = None
    status: Optional[TaskStatus] = None


class TaskResponse(BaseModel):
    """Task response schema."""
    id: str
    meeting_id: str
    title: str
    description: Optional[str] = None
    assignee: Optional[str] = None
    assignee_email: Optional[str] = None
    priority: TaskPriority
    due_date: Optional[date] = None
    due_date_text: Optional[str] = None
    status: TaskStatus
    source_text: Optional[str] = None
    extraction_confidence: Optional[float] = None
    external_id: Optional[str] = None
    external_service: Optional[str] = None
    external_url: Optional[str] = None
    synced_at: Optional[datetime] = None
    is_user_modified: bool
    is_duplicate: bool
    similarity_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Task list response."""
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskBulkAction(BaseModel):
    """Bulk task action request."""
    task_ids: List[str]
    action: str = Field(..., pattern="^(approve|reject|delete|sync)$")
    target_integration: Optional[str] = None  # For sync action


class TaskSyncRequest(BaseModel):
    """Request to sync tasks to external service."""
    task_ids: List[str]
    integration_id: str


class TaskSyncResult(BaseModel):
    """Result of task sync operation."""
    task_id: str
    success: bool
    external_id: Optional[str] = None
    external_url: Optional[str] = None
    error: Optional[str] = None
