"""
Base Integration Adapter
Abstract base class for project management tool integrations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from app.models.integration import Integration
from app.models.task import Task, TaskPriority


@dataclass
class TaskPayload:
    """Standardized task payload for external services."""
    title: str
    description: Optional[str] = None
    assignee: Optional[str] = None
    assignee_email: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[date] = None
    
    @classmethod
    def from_task(cls, task: Task) -> "TaskPayload":
        """Create payload from Task model."""
        return cls(
            title=task.title,
            description=task.description,
            assignee=task.assignee,
            assignee_email=task.assignee_email,
            priority=task.priority,
            due_date=task.due_date,
        )


@dataclass
class SyncResult:
    """Result of a task sync operation."""
    success: bool
    external_id: Optional[str] = None
    external_url: Optional[str] = None
    error: Optional[str] = None


class BaseIntegrationAdapter(ABC):
    """
    Abstract base class for project management integrations.
    Implements the Adapter pattern for uniform task syncing.
    """
    
    def __init__(self, integration: Integration):
        self.integration = integration
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the name of the service (e.g., 'asana', 'trello')."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the integration connection is valid."""
        pass
    
    @abstractmethod
    async def create_task(self, payload: TaskPayload) -> SyncResult:
        """
        Create a task in the external service.
        
        Args:
            payload: Standardized task data
            
        Returns:
            SyncResult with external ID and URL if successful
        """
        pass
    
    @abstractmethod
    async def update_task(
        self,
        external_id: str,
        payload: TaskPayload,
    ) -> SyncResult:
        """Update an existing task in the external service."""
        pass
    
    @abstractmethod
    async def delete_task(self, external_id: str) -> SyncResult:
        """Delete a task from the external service."""
        pass
    
    @abstractmethod
    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get available workspaces/boards."""
        pass
    
    @abstractmethod
    async def get_projects(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get projects/lists within a workspace."""
        pass
    
    def _map_priority(self, priority: TaskPriority) -> str:
        """Map internal priority to service-specific format. Override in subclass."""
        return priority.value
