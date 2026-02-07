"""
Trello Integration Adapter
Sync tasks to Trello boards.
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


class TrelloAdapter(BaseIntegrationAdapter):
    """Adapter for Trello integration."""
    
    BASE_URL = "https://api.trello.com/1"
    
    # Priority to label color mapping
    PRIORITY_COLORS = {
        TaskPriority.LOW: "green",
        TaskPriority.MEDIUM: "yellow",
        TaskPriority.HIGH: "orange",
        TaskPriority.URGENT: "red",
    }
    
    def __init__(self, integration: Integration):
        super().__init__(integration)
        self.api_key = integration.api_key or settings.trello_api_key
        self.api_token = integration.access_token
    
    @property
    def service_name(self) -> str:
        return "trello"
    
    @property
    def auth_params(self) -> Dict[str, str]:
        """Get authentication parameters for API calls."""
        return {
            "key": self.api_key,
            "token": self.api_token,
        }
    
    async def test_connection(self) -> bool:
        """Test Trello API connection."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/members/me",
                    params=self.auth_params,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.error("Trello connection test failed", error=str(e))
            return False
    
    async def create_task(self, payload: TaskPayload) -> SyncResult:
        """Create a card in Trello."""
        try:
            if not self.integration.list_id:
                return SyncResult(
                    success=False,
                    error="No Trello list configured",
                )
            
            # Build card data
            card_data = {
                **self.auth_params,
                "idList": self.integration.list_id,
                "name": payload.title,
            }
            
            if payload.description:
                card_data["desc"] = payload.description
            
            if payload.due_date:
                card_data["due"] = payload.due_date.isoformat()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/cards",
                    params=card_data,
                    timeout=30.0,
                )
                
                if response.status_code not in (200, 201):
                    return SyncResult(
                        success=False,
                        error=f"Trello API error: {response.status_code}",
                    )
                
                result = response.json()
                card_id = result["id"]
                
                # Add priority label
                await self._add_priority_label(card_id, payload.priority)
                
                return SyncResult(
                    success=True,
                    external_id=card_id,
                    external_url=result.get("shortUrl") or result.get("url"),
                )
                
        except Exception as e:
            logger.error("Trello card creation failed", error=str(e))
            return SyncResult(success=False, error=str(e))
    
    async def _add_priority_label(
        self,
        card_id: str,
        priority: TaskPriority,
    ) -> bool:
        """Add a colored label for priority."""
        try:
            color = self.PRIORITY_COLORS.get(priority, "yellow")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/cards/{card_id}/labels",
                    params={
                        **self.auth_params,
                        "color": color,
                        "name": priority.value.upper(),
                    },
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
        """Update an existing Trello card."""
        try:
            card_data = {
                **self.auth_params,
                "name": payload.title,
            }
            
            if payload.description:
                card_data["desc"] = payload.description
            
            if payload.due_date:
                card_data["due"] = payload.due_date.isoformat()
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.BASE_URL}/cards/{external_id}",
                    params=card_data,
                    timeout=30.0,
                )
                
                if response.status_code != 200:
                    return SyncResult(success=False, error="Update failed")
                
                return SyncResult(success=True, external_id=external_id)
                
        except Exception as e:
            return SyncResult(success=False, error=str(e))
    
    async def delete_task(self, external_id: str) -> SyncResult:
        """Delete a Trello card."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.BASE_URL}/cards/{external_id}",
                    params=self.auth_params,
                    timeout=10.0,
                )
                
                return SyncResult(success=response.status_code == 200)
                
        except Exception as e:
            return SyncResult(success=False, error=str(e))
    
    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get user's Trello boards (as workspaces)."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/members/me/boards",
                    params=self.auth_params,
                    timeout=10.0,
                )
                
                if response.status_code != 200:
                    raise IntegrationError(
                        "Failed to fetch Trello boards",
                        provider="trello",
                    )
                
                boards = response.json()
                return [
                    {"id": b["id"], "name": b["name"]}
                    for b in boards
                    if not b.get("closed")
                ]
                
        except Exception as e:
            logger.error("Failed to get Trello boards", error=str(e))
            raise IntegrationError(str(e), provider="trello")
    
    async def get_projects(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get lists in a Trello board (as projects)."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/boards/{workspace_id}/lists",
                    params=self.auth_params,
                    timeout=10.0,
                )
                
                if response.status_code != 200:
                    raise IntegrationError(
                        "Failed to fetch Trello lists",
                        provider="trello",
                    )
                
                lists = response.json()
                return [
                    {"id": l["id"], "name": l["name"], "board_id": workspace_id}
                    for l in lists
                    if not l.get("closed")
                ]
                
        except Exception as e:
            logger.error("Failed to get Trello lists", error=str(e))
            raise IntegrationError(str(e), provider="trello")
