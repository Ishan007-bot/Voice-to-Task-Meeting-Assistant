"""User Repository"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_active_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Get all active users."""
        result = await self.session.execute(
            select(User)
            .where(User.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def update_last_login(self, user_id: str) -> Optional[User]:
        """Update user's last login timestamp."""
        from datetime import datetime, timezone
        
        return await self.update(
            user_id,
            {"last_login": datetime.now(timezone.utc)}
        )
    
    async def verify_user(self, user_id: str) -> Optional[User]:
        """Mark user as verified."""
        from datetime import datetime, timezone
        
        return await self.update(
            user_id,
            {
                "is_verified": True,
                "verified_at": datetime.now(timezone.utc),
            }
        )
