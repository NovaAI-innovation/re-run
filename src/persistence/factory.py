"""Factory for creating persistence storage instances."""

from pathlib import Path
from typing import Optional

from .interface import ConversationPersistenceInterface
from .json_storage import JsonConversationStorage
from .db_storage import DatabaseConversationStorage
from ..config.settings import Settings


class PersistenceFactory:
    """Factory for creating conversation persistence storage instances."""
    
    @staticmethod
    def create_storage(settings: Settings) -> Optional[ConversationPersistenceInterface]:
        """
        Create conversation storage based on settings.
        
        Args:
            settings: Application settings
            
        Returns:
            ConversationPersistenceInterface instance or None if disabled
        """
        if not settings.persistence_enabled:
            return None
        
        if settings.persistence_type == "json":
            return JsonConversationStorage(
                storage_dir=Path(settings.json_storage_dir),
                max_conversations_per_user=settings.max_conversations_per_user
            )
        
        elif settings.persistence_type == "database":
            return DatabaseConversationStorage(
                database_url=settings.database_url,
                max_conversations_per_user=settings.max_conversations_per_user
            )
        
        else:
            raise ValueError(f"Unknown persistence type: {settings.persistence_type}")
