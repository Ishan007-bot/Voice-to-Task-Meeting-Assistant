"""
Asana Integration Adapter
Sync tasks to Asana projects.
"""

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import IntegrationError
from app.core.logging import get_logger
from app.integrations.base import (
    BaseIntegrationAdapter,
    SyncResult,
    TaskPayload,
)
from app.models.integration import Integration
from app.models.task import TaskPriority

logger = get_logger(__name__)


class AsanaAdapter(BaseIntegrationAdapter):
    """Adapter for Asana integration."""
    
    BASE_URL = "https://app.asana.com/api/1.0"
    
    def __init__(self, integration: Integration):
        super().__init__(integration)
        self.access_token = integration.access_token or settings.asana_personal_access_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    @property
    def service_name(self) -> str:
        return "asana"
    
    async def test_connection(self) -> bool:
        """Test Asana API connection."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/users/me",
                    headers=self.headers,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error("Asana connection test failed", error=str(e))
            return False
    
    async def create_task(self, payload: TaskPayload) -> SyncResult:
        """Create a task in Asana."""
        try:
            if not self.integration.project_id:
                return SyncResult(
                    success=False,
                    error="No Asana project configured",
                )
            
            # Build task data
            task_data = {
                "data": {
                    "name": payload.title,
                    "projects": [self.integration.project_id],
                }
            }
            
            if payload.description:
                task_data["data"]["notes"] = payload.description
            
            if payload.due_date:
                task_data["data"]["due_on"] = payload.due_date.isoformat()
            
            # Map priority to custom field or tag if configured
            # Asana doesn't have native priority, could use custom fields
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/tasks",
                    headers=self.headers,
                    json=task_data,
                    timeout=30.0,
                )
                
                if response.status_code not in (200, 201):
                    error_msg = response.json().get("errors", [{}])[0].get("message", "Unknown error")
                    return SyncResult(success=False, error=error_msg)
                
                result = response.json()["data"]
                task_gid = result["gid"]
                
                # Try to assign if we have assignee email
                if payload.assignee_email:
                    await self._assign_task(task_gid, payload.assignee_email)
                
                return SyncResult(
                    success=True,
                    external_id=task_gid,
                    external_url=f"https://app.asana.com/0/{self.integration.project_id}/{task_gid}",
                )
                
        except Exception as e:
            logger.error("Asana task creation failed", error=str(e))
            return SyncResult(success=False, error=str(e))
    
    async def _assign_task(self, task_gid: str, assignee_email: str) -> bool:
        """Assign task to user by email."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/tasks/{task_gid}",
                    headers=self.headers,
                    json={"data": {"assignee": assignee_email}},
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception:
            return False
    
    async def update_task(
        self,
        external_id: str,
        payload: TaskPayload,
    ) -> SyncResult:
        """Update an existing Asana task."""
        try:
            task_data = {"data": {"name": payload.title}}
            
            if payload.description:
                task_data["data"]["notes"] = payload.description
            
            if payload.due_date:
                task_data["data"]["due_on"] = payload.due_date.isoformat()
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/tasks/{external_id}",
                    headers=self.headers,
                    json=task_data,
                    timeout=30.0,
                )
                
                if response.status_code != 200:
                    return SyncResult(success=False, error="Update failed")
                
                return SyncResult(success=True, external_id=external_id)
                
        except Exception as e:
            return SyncResult(success=False, error=str(e))
    
    async def delete_task(self, external_id: str) -> SyncResult:
        """Delete an Asana task."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.BASE_URL}/tasks/{external_id}",
                    headers=self.headers,
                    timeout=10.0,
                )
                
                return SyncResult(success=response.status_code in (200, 204))
                
        except Exception as e:
            return SyncResult(success=False, error=str(e))
    
    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get user's Asana workspaces."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/workspaces",
                    headers=self.headers,
                    timeout=10.0,
                )
                
                if response.status_code != 200:
                    raise IntegrationError(
                        "Failed to fetch Asana workspaces",
                        provider="asana",
                    )
                
                return response.json()["data"]
                
        except Exception as e:
            logger.error("Failed to get Asana workspaces", error=str(e))
            raise IntegrationError(str(e), provider="asana")
    
    async def get_projects(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get projects in an Asana workspace."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/projects",
                    headers=self.headers,
                    params={"workspace": workspace_id},
                    timeout=10.0,
                )
                
                if response.status_code != 200:
                    raise IntegrationError(
                        "Failed to fetch Asana projects",
                        provider="asana",
                    )
                
                return response.json()["data"]
                
        except Exception as e:
            logger.error("Failed to get Asana projects", error=str(e))
            raise IntegrationError(str(e), provider="asana")
