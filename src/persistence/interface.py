"""Abstract interface for conversation persistence."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import UserConversation, ConversationMessage, ConversationSummary, ConversationStats, MessageRole


class ConversationPersistenceInterface(ABC):
    """Abstract interface for conversation persistence implementations."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the persistence backend."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the persistence backend gracefully."""
        pass
    
    # Conversation Management
    @abstractmethod
    async def get_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> Optional[UserConversation]:
        """
        Get conversation for a user.
        
        Args:
            user_id: User identifier
            conversation_id: Optional specific conversation ID. If None, gets the active conversation.
            
        Returns:
            UserConversation if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def create_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> UserConversation:
        """
        Create a new conversation for a user.
        
        Args:
            user_id: User identifier
            conversation_id: Optional conversation ID. If None, generates one.
            
        Returns:
            Created UserConversation
        """
        pass
    
    @abstractmethod
    async def save_conversation(self, conversation: UserConversation) -> None:
        """
        Save conversation to storage.
        
        Args:
            conversation: UserConversation to save
        """
        pass
    
    @abstractmethod
    async def list_conversations(self, user_id: str, limit: int = 10, offset: int = 0) -> List[UserConversation]:
        """
        List conversations for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            
        Returns:
            List of UserConversation objects
        """
        pass
    
    @abstractmethod
    async def archive_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Archive (mark inactive) a conversation.
        
        Args:
            user_id: User identifier
            conversation_id: Conversation identifier
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete a conversation permanently.
        
        Args:
            user_id: User identifier
            conversation_id: Conversation identifier
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    # Message Management
    @abstractmethod
    async def add_message(
        self, 
        user_id: str, 
        role: MessageRole, 
        content: str, 
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationMessage:
        """
        Add a message to a conversation.
        
        Args:
            user_id: User identifier
            role: Message role
            content: Message content
            conversation_id: Optional conversation ID. If None, uses active conversation.
            metadata: Optional message metadata
            
        Returns:
            Created ConversationMessage
        """
        pass
    
    @abstractmethod
    async def get_context_messages(
        self, 
        user_id: str, 
        conversation_id: Optional[str] = None,
        include_summary: bool = True
    ) -> List[ConversationMessage]:
        """
        Get context messages for AI agent.
        
        Args:
            user_id: User identifier
            conversation_id: Optional conversation ID. If None, uses active conversation.
            include_summary: Whether to include conversation summary
            
        Returns:
            List of ConversationMessage for context
        """
        pass
    
    # Summary Management
    @abstractmethod
    async def create_summary(
        self, 
        user_id: str, 
        conversation_id: str, 
        summary: str, 
        key_topics: List[str]
    ) -> ConversationSummary:
        """
        Create a conversation summary.
        
        Args:
            user_id: User identifier
            conversation_id: Conversation identifier
            summary: Summary text
            key_topics: List of key topics
            
        Returns:
            Created ConversationSummary
        """
        pass
    
    # Statistics and Analytics
    @abstractmethod
    async def get_user_stats(self, user_id: str) -> ConversationStats:
        """
        Get conversation statistics for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            ConversationStats object
        """
        pass
    
    @abstractmethod
    async def cleanup_old_data(self, days: int = 30) -> int:
        """
        Clean up old conversation data.
        
        Args:
            days: Number of days to retain data
            
        Returns:
            Number of items cleaned up
        """
        pass
    
    # Health and Maintenance
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on persistence backend.
        
        Returns:
            Health check results
        """
        pass
