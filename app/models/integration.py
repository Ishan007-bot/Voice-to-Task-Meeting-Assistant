"""Integration Model for External Services"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class IntegrationType(str, enum.Enum):
    """Supported integration types."""
    ASANA = "asana"
    TRELLO = "trello"
    JIRA = "jira"


class Integration(Base):
    """User's integration with external project management tools."""
    
    __tablename__ = "integrations"
    
    # User relationship
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    
    # Integration type
    integration_type: Mapped[IntegrationType] = mapped_column(
        Enum(IntegrationType),
        index=True,
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # OAuth tokens (encrypted in production)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # API key authentication (alternative to OAuth)
    api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_secret: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Service-specific configuration
    workspace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    workspace_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    board_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # For Trello
    list_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # For Trello
    
    # Account info from external service
    external_user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Sync settings
    auto_sync_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Error tracking
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_count: Mapped[int] = mapped_column(default=0)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="integrations")
    
    def __repr__(self) -> str:
        return f"<Integration {self.integration_type.value} for User {self.user_id}>"
