"""Integration Endpoints"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.integration import Integration, IntegrationType
from app.models.user import User
from app.repositories.integration import IntegrationRepository
from app.schemas.integration import (
    IntegrationCreate,
    IntegrationListResponse,
    IntegrationResponse,
    IntegrationUpdate,
)
from app.integrations.factory import IntegrationFactory
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IntegrationListResponse:
    """List all integrations for the current user."""
    integration_repo = IntegrationRepository(db)
    
    integrations = await integration_repo.get_user_integrations(
        user_id=current_user.id,
        active_only=False,
    )
    
    return IntegrationListResponse(
        items=[IntegrationResponse.model_validate(i) for i in integrations]
    )


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    integration_data: IntegrationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Integration:
    """Create a new integration."""
    integration_repo = IntegrationRepository(db)
    
    # Check if integration of this type already exists
    existing = await integration_repo.get_user_integration_by_type(
        user_id=current_user.id,
        integration_type=integration_data.integration_type,
    )
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integration for {integration_data.integration_type.value} already exists",
        )
    
    integration = await integration_repo.create({
        "user_id": current_user.id,
        **integration_data.model_dump(),
    })
    
    return integration


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Integration:
    """Get integration by ID."""
    integration_repo = IntegrationRepository(db)
    
    integration = await integration_repo.get_by_id(integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    return integration


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    integration_update: IntegrationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Integration:
    """Update integration settings."""
    integration_repo = IntegrationRepository(db)
    
    integration = await integration_repo.get_by_id(integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    updated = await integration_repo.update(
        integration_id,
        integration_update.model_dump(exclude_unset=True),
    )
    
    return updated


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an integration."""
    integration_repo = IntegrationRepository(db)
    
    integration = await integration_repo.get_by_id(integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    await integration_repo.delete(integration_id)


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test integration connection."""
    integration_repo = IntegrationRepository(db)
    
    integration = await integration_repo.get_by_id(integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    try:
        adapter = IntegrationFactory.create(integration)
        is_connected = await adapter.test_connection()
        
        if is_connected:
            await integration_repo.clear_error(integration_id)
        else:
            await integration_repo.record_error(integration_id, "Connection test failed")
        
        return {
            "success": is_connected,
            "message": "Connection successful" if is_connected else "Connection failed",
        }
    except Exception as e:
        await integration_repo.record_error(integration_id, str(e))
        return {
            "success": False,
            "message": str(e),
        }


@router.get("/{integration_id}/workspaces")
async def get_workspaces(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get available workspaces/boards from integration."""
    integration_repo = IntegrationRepository(db)
    
    integration = await integration_repo.get_by_id(integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    try:
        adapter = IntegrationFactory.create(integration)
        workspaces = await adapter.get_workspaces()
        return {"workspaces": workspaces}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


@router.get("/{integration_id}/projects/{workspace_id}")
async def get_projects(
    integration_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get projects/lists within a workspace."""
    integration_repo = IntegrationRepository(db)
    
    integration = await integration_repo.get_by_id(integration_id)
    if not integration or integration.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    try:
        adapter = IntegrationFactory.create(integration)
        projects = await adapter.get_projects(workspace_id)
        return {"projects": projects}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


@router.get("/types/available")
async def get_available_integration_types() -> dict:
    """Get list of supported integration types."""
    return {
        "types": IntegrationFactory.get_supported_types()
    }
