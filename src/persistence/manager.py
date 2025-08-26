"""Conversation persistence manager."""

from typing import Optional, List, Dict, Any
import logging

from .interface import ConversationPersistenceInterface
from .models import ConversationMessage, MessageRole, ConversationStats
from ..config.settings import Settings


logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages conversation persistence and provides high-level operations."""
    
    def __init__(self, storage: Optional[ConversationPersistenceInterface], settings: Settings):
        """
        Initialize conversation manager.
        
        Args:
            storage: Persistence storage instance (None if disabled)
            settings: Application settings
        """
        self.storage = storage
        self.settings = settings
        self.enabled = storage is not None
    
    async def initialize(self) -> None:
        """Initialize the conversation manager."""
        if self.storage:
            await self.storage.initialize()
            logger.info("Conversation persistence initialized")
        else:
            logger.info("Conversation persistence disabled")
    
    async def shutdown(self) -> None:
        """Shutdown the conversation manager."""
        if self.storage:
            await self.storage.shutdown()
            logger.info("Conversation persistence shutdown")
    
    async def add_user_message(self, user_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a user message to conversation.
        
        Args:
            user_id: User identifier
            content: Message content
            metadata: Optional message metadata
            
        Returns:
            True if successful, False if persistence disabled
        """
        if not self.enabled:
            return False
        
        try:
            await self.storage.add_message(
                user_id=user_id,
                role=MessageRole.USER,
                content=content,
                metadata=metadata
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to add user message for {user_id}: {e}")
            return False
    
    async def add_assistant_message(self, user_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add an assistant message to conversation.
        
        Args:
            user_id: User identifier
            content: Message content
            metadata: Optional message metadata
            
        Returns:
            True if successful, False if persistence disabled
        """
        if not self.enabled:
            return False
        
        try:
            await self.storage.add_message(
                user_id=user_id,
                role=MessageRole.ASSISTANT,
                content=content,
                metadata=metadata
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to add assistant message for {user_id}: {e}")
            return False
    
    async def get_conversation_context(self, user_id: str) -> List[ConversationMessage]:
        """
        Get conversation context for AI agent.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of context messages (empty if disabled)
        """
        if not self.enabled:
            return []
        
        try:
            return await self.storage.get_context_messages(user_id, include_summary=True)
            
        except Exception as e:
            logger.error(f"Failed to get conversation context for {user_id}: {e}")
            return []
    
    async def should_summarize_conversation(self, user_id: str) -> bool:
        """
        Check if conversation should be summarized.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if should summarize, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            conversation = await self.storage.get_conversation(user_id)
            if conversation:
                return conversation.should_summarize(self.settings.auto_summarize_threshold)
            
        except Exception as e:
            logger.error(f"Failed to check summarization status for {user_id}: {e}")
        
        return False
    
    async def create_conversation_summary(self, user_id: str, summary: str, key_topics: List[str]) -> bool:
        """
        Create a conversation summary.
        
        Args:
            user_id: User identifier
            summary: Summary text
            key_topics: List of key topics
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            conversation = await self.storage.get_conversation(user_id)
            if conversation:
                await self.storage.create_summary(
                    user_id=user_id,
                    conversation_id=conversation.conversation_id,
                    summary=summary,
                    key_topics=key_topics
                )
                return True
            
        except Exception as e:
            logger.error(f"Failed to create summary for {user_id}: {e}")
        
        return False
    
    async def clear_conversation_history(self, user_id: str) -> bool:
        """
        Clear conversation history for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            conversation = await self.storage.get_conversation(user_id)
            if conversation:
                await self.storage.archive_conversation(user_id, conversation.conversation_id)
                return True
            
        except Exception as e:
            logger.error(f"Failed to clear conversation for {user_id}: {e}")
        
        return False
    
    async def get_user_stats(self, user_id: str) -> Optional[ConversationStats]:
        """
        Get conversation statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            ConversationStats or None if disabled/failed
        """
        if not self.enabled:
            return None
        
        try:
            return await self.storage.get_user_stats(user_id)
            
        except Exception as e:
            logger.error(f"Failed to get stats for {user_id}: {e}")
            return None
    
    async def cleanup_old_conversations(self) -> int:
        """
        Clean up old conversations.
        
        Returns:
            Number of conversations cleaned up
        """
        if not self.enabled:
            return 0
        
        try:
            return await self.storage.cleanup_old_data(self.settings.cleanup_old_data_days)
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on persistence system.
        
        Returns:
            Health check results
        """
        if not self.enabled:
            return {
                "enabled": False,
                "healthy": True,
                "message": "Persistence disabled"
            }
        
        try:
            health_data = await self.storage.health_check()
            health_data["enabled"] = True
            return health_data
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "enabled": True,
                "healthy": False,
                "error": str(e)
            }
