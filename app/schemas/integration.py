"""Integration Pydantic Schemas"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.integration import IntegrationType


class IntegrationCreate(BaseModel):
    """Integration creation schema."""
    integration_type: IntegrationType
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    board_id: Optional[str] = None
    list_id: Optional[str] = None


class IntegrationUpdate(BaseModel):
    """Integration update schema."""
    is_active: Optional[bool] = None
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    board_id: Optional[str] = None
    list_id: Optional[str] = None
    auto_sync_enabled: Optional[bool] = None


class IntegrationResponse(BaseModel):
    """Integration response schema."""
    id: str
    user_id: str
    integration_type: IntegrationType
    is_active: bool
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    board_id: Optional[str] = None
    list_id: Optional[str] = None
    external_user_name: Optional[str] = None
    external_user_email: Optional[str] = None
    auto_sync_enabled: bool
    last_synced_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IntegrationListResponse(BaseModel):
    """Integration list response."""
    items: List[IntegrationResponse]


class OAuthCallbackData(BaseModel):
    """OAuth callback data."""
    code: str
    state: Optional[str] = None


class AsanaWorkspace(BaseModel):
    """Asana workspace info."""
    gid: str
    name: str


class AsanaProject(BaseModel):
    """Asana project info."""
    gid: str
    name: str
    workspace_gid: str


class TrelloBoard(BaseModel):
    """Trello board info."""
    id: str
    name: str


class TrelloList(BaseModel):
    """Trello list info."""
    id: str
    name: str
    board_id: str
