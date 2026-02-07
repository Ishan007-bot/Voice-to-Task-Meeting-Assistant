"""
Integration Factory
Factory pattern for creating integration adapters.
"""

from typing import Optional

from app.core.exceptions import IntegrationError
from app.integrations.asana import AsanaAdapter
from app.integrations.base import BaseIntegrationAdapter
from app.integrations.trello import TrelloAdapter
from app.models.integration import Integration, IntegrationType


class IntegrationFactory:
    """Factory for creating integration adapters."""
    
    _adapters = {
        IntegrationType.ASANA: AsanaAdapter,
        IntegrationType.TRELLO: TrelloAdapter,
        # Add JIRA adapter when implemented
        # IntegrationType.JIRA: JiraAdapter,
    }
    
    @classmethod
    def create(cls, integration: Integration) -> BaseIntegrationAdapter:
        """
        Create an adapter instance for the given integration.
        
        Args:
            integration: Integration model instance
            
        Returns:
            Configured adapter instance
            
        Raises:
            IntegrationError: If integration type is not supported
        """
        adapter_class = cls._adapters.get(integration.integration_type)
        
        if not adapter_class:
            raise IntegrationError(
                f"Integration type '{integration.integration_type}' is not supported",
                provider=integration.integration_type.value,
            )
        
        return adapter_class(integration)
    
    @classmethod
    def get_supported_types(cls) -> list[str]:
        """Get list of supported integration types."""
        return [t.value for t in cls._adapters.keys()]
