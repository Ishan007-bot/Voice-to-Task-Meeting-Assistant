"""
Authentication Service
Handles user authentication, registration, and token management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, DuplicateError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_refresh_token,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import TokenResponse, UserCreate, UserResponse

logger = get_logger(__name__)


class AuthService:
    """Service for authentication and user management."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
    
    async def register(self, user_data: UserCreate) -> User:
        """
        Register a new user.
        
        Args:
            user_data: User registration data
            
        Returns:
            Created user object
            
        Raises:
            DuplicateError: If email already exists
        """
        # Check for existing user
        existing = await self.user_repo.get_by_email(user_data.email)
        if existing:
            raise DuplicateError(
                "Email already registered",
                details={"email": user_data.email},
            )
        
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Create user
        user = await self.user_repo.create({
            "email": user_data.email,
            "full_name": user_data.full_name,
            "hashed_password": hashed_password,
        })
        
        logger.info("User registered", user_id=user.id, email=user.email)
        return user
    
    async def authenticate(
        self,
        email: str,
        password: str,
    ) -> Tuple[User, TokenResponse]:
        """
        Authenticate user and return tokens.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Tuple of (user, token_response)
            
        Raises:
            AuthenticationError: If credentials are invalid
        """
        # Get user
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise AuthenticationError("Invalid email or password")
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        
        # Check if user is active
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")
        
        # Generate tokens
        tokens = self._create_tokens(user)
        
        # Update last login
        await self.user_repo.update_last_login(user.id)
        
        logger.info("User authenticated", user_id=user.id)
        return user, tokens
    
    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token response
            
        Raises:
            AuthenticationError: If refresh token is invalid
        """
        # Verify refresh token
        payload = verify_refresh_token(refresh_token)
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid refresh token")
        
        # Get user
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        
        # Generate new tokens
        tokens = self._create_tokens(user)
        
        logger.info("Tokens refreshed", user_id=user.id)
        return tokens
    
    async def get_current_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return await self.user_repo.get_by_id(user_id)
    
    async def update_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """
        Update user password.
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            
        Returns:
            True if successful
            
        Raises:
            AuthenticationError: If current password is wrong
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")
        
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        
        hashed = get_password_hash(new_password)
        await self.user_repo.update(user_id, {"hashed_password": hashed})
        
        logger.info("Password updated", user_id=user_id)
        return True
    
    def _create_tokens(self, user: User) -> TokenResponse:
        """Create access and refresh tokens for user."""
        access_token = create_access_token(
            data={"sub": user.id, "email": user.email}
        )
        
        refresh_token = create_refresh_token(
            data={"sub": user.id}
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
