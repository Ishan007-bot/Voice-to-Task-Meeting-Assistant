"""Integration Repository"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration, IntegrationType
from app.repositories.base import BaseRepository


class IntegrationRepository(BaseRepository[Integration]):
    """Repository for Integration operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Integration, session)
    
    async def get_user_integrations(
        self,
        user_id: str,
        active_only: bool = True,
    ) -> List[Integration]:
        """Get all integrations for a user."""
        query = select(Integration).where(Integration.user_id == user_id)
        
        if active_only:
            query = query.where(Integration.is_active == True)
        
        query = query.order_by(Integration.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_user_integration_by_type(
        self,
        user_id: str,
        integration_type: IntegrationType,
    ) -> Optional[Integration]:
        """Get a specific integration type for a user."""
        result = await self.session.execute(
            select(Integration)
            .where(Integration.user_id == user_id)
            .where(Integration.integration_type == integration_type)
            .where(Integration.is_active == True)
        )
        return result.scalar_one_or_none()
    
    async def update_tokens(
        self,
        integration_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> Optional[Integration]:
        """Update OAuth tokens for an integration."""
        update_data = {"access_token": access_token}
        
        if refresh_token:
            update_data["refresh_token"] = refresh_token
        if expires_at:
            update_data["token_expires_at"] = expires_at
        
        return await self.update(integration_id, update_data)
    
    async def record_error(
        self,
        integration_id: str,
        error_message: str,
    ) -> Optional[Integration]:
        """Record an error for an integration."""
        integration = await self.get_by_id(integration_id)
        if integration:
            return await self.update(
                integration_id,
                {
                    "last_error": error_message,
                    "error_count": integration.error_count + 1,
                }
            )
        return None
    
    async def clear_error(self, integration_id: str) -> Optional[Integration]:
        """Clear error status for an integration."""
        return await self.update(
            integration_id,
            {
                "last_error": None,
                "error_count": 0,
            }
        )
    
    async def update_sync_timestamp(
        self,
        integration_id: str,
    ) -> Optional[Integration]:
        """Update last synced timestamp."""
        from datetime import datetime, timezone
        
        return await self.update(
            integration_id,
            {"last_synced_at": datetime.now(timezone.utc)}
        )
    
    async def deactivate(self, integration_id: str) -> Optional[Integration]:
        """Deactivate an integration."""
        return await self.update(
            integration_id,
            {
                "is_active": False,
                "access_token": None,
                "refresh_token": None,
            }
        )
