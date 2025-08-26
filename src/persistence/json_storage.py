"""JSON-based conversation storage implementation."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from .interface import ConversationPersistenceInterface
from .models import (
    UserConversation, 
    ConversationMessage, 
    ConversationSummary, 
    ConversationStats, 
    MessageRole
)


logger = logging.getLogger(__name__)


class JsonConversationStorage(ConversationPersistenceInterface):
    """JSON file-based conversation storage implementation."""
    
    def __init__(self, storage_dir: Path = None, max_conversations_per_user: int = 100):
        """
        Initialize JSON storage.
        
        Args:
            storage_dir: Directory to store conversation files
            max_conversations_per_user: Maximum conversations to keep per user
        """
        self.storage_dir = storage_dir or Path("data/conversations")
        self.max_conversations_per_user = max_conversations_per_user
        self._lock = asyncio.Lock()
        self._cache: Dict[str, UserConversation] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=30)
    
    async def initialize(self) -> None:
        """Initialize the storage directory."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initialized JSON storage at {self.storage_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize JSON storage: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown gracefully - flush cache."""
        async with self._lock:
            await self._flush_cache()
            self._cache.clear()
            self._cache_expiry.clear()
        logger.info("JSON storage shutdown complete")
    
    def _get_user_dir(self, user_id: str) -> Path:
        """Get user-specific storage directory."""
        return self.storage_dir / user_id
    
    def _get_conversation_file(self, user_id: str, conversation_id: str) -> Path:
        """Get conversation file path."""
        return self._get_user_dir(user_id) / f"{conversation_id}.json"
    
    def _get_cache_key(self, user_id: str, conversation_id: str) -> str:
        """Get cache key for conversation."""
        return f"{user_id}:{conversation_id}"
    
    async def _load_conversation_from_file(self, user_id: str, conversation_id: str) -> Optional[UserConversation]:
        """Load conversation from JSON file."""
        conversation_file = self._get_conversation_file(user_id, conversation_id)
        
        if not conversation_file.exists():
            return None
        
        try:
            with open(conversation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Parse datetime strings back to datetime objects
            conversation = UserConversation.model_validate(data)
            return conversation
            
        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id} for user {user_id}: {e}")
            return None
    
    async def _save_conversation_to_file(self, conversation: UserConversation) -> None:
        """Save conversation to JSON file."""
        user_dir = self._get_user_dir(conversation.user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        conversation_file = self._get_conversation_file(conversation.user_id, conversation.conversation_id)
        
        try:
            # Use Pydantic's model_dump_json for proper serialization
            conversation_data = conversation.model_dump_json(indent=2)
            
            with open(conversation_file, 'w', encoding='utf-8') as f:
                f.write(conversation_data)
                
        except Exception as e:
            logger.error(f"Failed to save conversation {conversation.conversation_id} for user {conversation.user_id}: {e}")
            raise
    
    async def _get_cached_conversation(self, user_id: str, conversation_id: str) -> Optional[UserConversation]:
        """Get conversation from cache if valid."""
        cache_key = self._get_cache_key(user_id, conversation_id)
        
        if cache_key in self._cache:
            expiry = self._cache_expiry.get(cache_key)
            if expiry and datetime.utcnow() < expiry:
                return self._cache[cache_key]
            else:
                # Cache expired
                del self._cache[cache_key]
                if cache_key in self._cache_expiry:
                    del self._cache_expiry[cache_key]
        
        return None
    
    async def _cache_conversation(self, conversation: UserConversation) -> None:
        """Cache conversation with TTL."""
        cache_key = self._get_cache_key(conversation.user_id, conversation.conversation_id)
        self._cache[cache_key] = conversation
        self._cache_expiry[cache_key] = datetime.utcnow() + self._cache_ttl
    
    async def _flush_cache(self) -> None:
        """Flush all cached conversations to disk."""
        for conversation in self._cache.values():
            try:
                await self._save_conversation_to_file(conversation)
            except Exception as e:
                logger.error(f"Failed to flush conversation {conversation.conversation_id}: {e}")
    
    async def get_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> Optional[UserConversation]:
        """Get conversation for a user."""
        async with self._lock:
            if conversation_id is None:
                # Get active conversation
                conversations = await self._list_conversations_from_disk(user_id, active_only=True)
                if conversations:
                    return conversations[0]  # Most recent active
                return None
            
            # Check cache first
            cached = await self._get_cached_conversation(user_id, conversation_id)
            if cached:
                return cached
            
            # Load from disk
            conversation = await self._load_conversation_from_file(user_id, conversation_id)
            if conversation:
                await self._cache_conversation(conversation)
            
            return conversation
    
    async def create_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> UserConversation:
        """Create a new conversation for a user."""
        async with self._lock:
            if conversation_id is None:
                conversation_id = str(uuid.uuid4())
            
            conversation = UserConversation(
                user_id=user_id,
                conversation_id=conversation_id
            )
            
            await self._cache_conversation(conversation)
            await self._save_conversation_to_file(conversation)
            
            return conversation
    
    async def save_conversation(self, conversation: UserConversation) -> None:
        """Save conversation to storage."""
        async with self._lock:
            conversation.updated_at = datetime.utcnow()
            await self._cache_conversation(conversation)
            await self._save_conversation_to_file(conversation)
    
    async def _list_conversations_from_disk(self, user_id: str, active_only: bool = False) -> List[UserConversation]:
        """List conversations from disk."""
        user_dir = self._get_user_dir(user_id)
        
        if not user_dir.exists():
            return []
        
        conversations = []
        
        try:
            for conversation_file in user_dir.glob("*.json"):
                conversation_id = conversation_file.stem
                conversation = await self._load_conversation_from_file(user_id, conversation_id)
                
                if conversation:
                    if not active_only or conversation.is_active:
                        conversations.append(conversation)
        
        except Exception as e:
            logger.error(f"Failed to list conversations for user {user_id}: {e}")
        
        # Sort by updated_at descending (most recent first)
        conversations.sort(key=lambda c: c.updated_at, reverse=True)
        return conversations
    
    async def list_conversations(self, user_id: str, limit: int = 10, offset: int = 0) -> List[UserConversation]:
        """List conversations for a user."""
        conversations = await self._list_conversations_from_disk(user_id)
        return conversations[offset:offset + limit]
    
    async def archive_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Archive (mark inactive) a conversation."""
        conversation = await self.get_conversation(user_id, conversation_id)
        if not conversation:
            return False
        
        conversation.is_active = False
        await self.save_conversation(conversation)
        return True
    
    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a conversation permanently."""
        async with self._lock:
            conversation_file = self._get_conversation_file(user_id, conversation_id)
            
            if conversation_file.exists():
                try:
                    conversation_file.unlink()
                    
                    # Remove from cache
                    cache_key = self._get_cache_key(user_id, conversation_id)
                    if cache_key in self._cache:
                        del self._cache[cache_key]
                    if cache_key in self._cache_expiry:
                        del self._cache_expiry[cache_key]
                    
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete conversation {conversation_id}: {e}")
                    return False
            
            return False
    
    async def add_message(
        self, 
        user_id: str, 
        role: MessageRole, 
        content: str, 
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationMessage:
        """Add a message to a conversation."""
        conversation = await self.get_conversation(user_id, conversation_id)
        
        if not conversation:
            conversation = await self.create_conversation(user_id, conversation_id)
        
        message = conversation.add_message(role, content, metadata)
        await self.save_conversation(conversation)
        
        return message
    
    async def get_context_messages(
        self, 
        user_id: str, 
        conversation_id: Optional[str] = None,
        include_summary: bool = True
    ) -> List[ConversationMessage]:
        """Get context messages for AI agent."""
        conversation = await self.get_conversation(user_id, conversation_id)
        
        if not conversation:
            return []
        
        return conversation.get_recent_context(include_summary)
    
    async def create_summary(
        self, 
        user_id: str, 
        conversation_id: str, 
        summary: str, 
        key_topics: List[str]
    ) -> ConversationSummary:
        """Create a conversation summary."""
        conversation = await self.get_conversation(user_id, conversation_id)
        
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found for user {user_id}")
        
        conversation_summary = ConversationSummary(
            summary=summary,
            key_topics=key_topics,
            message_count=len(conversation.messages)
        )
        
        conversation.summaries.append(conversation_summary)
        await self.save_conversation(conversation)
        
        return conversation_summary
    
    async def get_user_stats(self, user_id: str) -> ConversationStats:
        """Get conversation statistics for a user."""
        conversations = await self._list_conversations_from_disk(user_id)
        
        total_messages = sum(len(conv.messages) for conv in conversations)
        active_conversations = sum(1 for conv in conversations if conv.is_active)
        
        last_activity = None
        if conversations:
            last_activity = max(conv.updated_at for conv in conversations)
        
        avg_messages = total_messages / len(conversations) if conversations else 0.0
        
        return ConversationStats(
            user_id=user_id,
            total_conversations=len(conversations),
            total_messages=total_messages,
            active_conversations=active_conversations,
            last_activity=last_activity,
            avg_messages_per_conversation=avg_messages
        )
    
    async def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old conversation data."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cleanup_count = 0
        
        async with self._lock:
            try:
                for user_dir in self.storage_dir.iterdir():
                    if not user_dir.is_dir():
                        continue
                    
                    for conversation_file in user_dir.glob("*.json"):
                        try:
                            conversation_id = conversation_file.stem
                            user_id = user_dir.name
                            conversation = await self._load_conversation_from_file(user_id, conversation_id)
                            
                            if conversation and conversation.updated_at < cutoff_date and not conversation.is_active:
                                conversation_file.unlink()
                                cleanup_count += 1
                                logger.debug(f"Cleaned up old conversation: {user_id}/{conversation_id}")
                                
                        except Exception as e:
                            logger.error(f"Error during cleanup of {conversation_file}: {e}")
                            
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        logger.info(f"Cleaned up {cleanup_count} old conversations")
        return cleanup_count
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on persistence backend."""
        try:
            # Check if storage directory is accessible
            storage_accessible = self.storage_dir.exists() and self.storage_dir.is_dir()
            
            # Count total conversations and users
            total_users = 0
            total_conversations = 0
            
            if storage_accessible:
                for user_dir in self.storage_dir.iterdir():
                    if user_dir.is_dir():
                        total_users += 1
                        total_conversations += len(list(user_dir.glob("*.json")))
            
            return {
                "healthy": storage_accessible,
                "storage_dir": str(self.storage_dir),
                "storage_accessible": storage_accessible,
                "total_users": total_users,
                "total_conversations": total_conversations,
                "cache_size": len(self._cache),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
