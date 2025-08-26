"""Database-based conversation storage implementation using SQLAlchemy."""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import and_, desc, func

from .interface import ConversationPersistenceInterface
from .models import (
    UserConversation, 
    ConversationMessage, 
    ConversationSummary, 
    ConversationStats, 
    MessageRole
)
from .database import (
    DatabaseManager,
    DBUserConversation,
    DBConversationMessage,
    DBConversationSummary
)


logger = logging.getLogger(__name__)


class DatabaseConversationStorage(ConversationPersistenceInterface):
    """Database-based conversation storage using SQLAlchemy."""
    
    def __init__(self, database_url: str, max_conversations_per_user: int = 100):
        """
        Initialize database storage.
        
        Args:
            database_url: SQLAlchemy database URL
            max_conversations_per_user: Maximum conversations to keep per user
        """
        self.database_url = database_url
        self.max_conversations_per_user = max_conversations_per_user
        self.db_manager = DatabaseManager(database_url)
    
    async def initialize(self) -> None:
        """Initialize the database."""
        try:
            self.db_manager.initialize()
            logger.info(f"Initialized database storage at {self.database_url}")
        except Exception as e:
            logger.error(f"Failed to initialize database storage: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown database gracefully."""
        self.db_manager.shutdown()
        logger.info("Database storage shutdown complete")
    
    def _db_to_pydantic_conversation(self, db_conversation: DBUserConversation) -> UserConversation:
        """Convert database model to Pydantic model."""
        messages = [
            ConversationMessage(
                id=msg.message_id,
                role=MessageRole(msg.role),
                content=msg.content,
                timestamp=msg.timestamp,
                metadata=msg.message_metadata or {}
            )
            for msg in sorted(db_conversation.messages, key=lambda m: m.timestamp)
        ]
        
        summaries = [
            ConversationSummary(
                summary=summ.summary,
                key_topics=summ.key_topics or [],
                created_at=summ.created_at,
                message_count=summ.message_count
            )
            for summ in sorted(db_conversation.summaries, key=lambda s: s.created_at)
        ]
        
        return UserConversation(
            user_id=db_conversation.user_id,
            conversation_id=db_conversation.conversation_id,
            messages=messages,
            summaries=summaries,
            created_at=db_conversation.created_at,
            updated_at=db_conversation.updated_at,
            is_active=db_conversation.is_active,
            context_window_size=db_conversation.context_window_size
        )
    
    def _pydantic_to_db_conversation(
        self, 
        conversation: UserConversation,
        db_conversation: Optional[DBUserConversation] = None
    ) -> DBUserConversation:
        """Convert Pydantic model to database model."""
        if db_conversation is None:
            db_conversation = DBUserConversation(
                user_id=conversation.user_id,
                conversation_id=conversation.conversation_id,
                created_at=conversation.created_at,
                is_active=conversation.is_active,
                context_window_size=conversation.context_window_size
            )
        
        # Update basic fields
        db_conversation.updated_at = conversation.updated_at
        db_conversation.is_active = conversation.is_active
        db_conversation.context_window_size = conversation.context_window_size
        
        return db_conversation
    
    async def get_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> Optional[UserConversation]:
        """Get conversation for a user."""
        with self.db_manager.get_session() as session:
            if conversation_id is None:
                # Get most recent active conversation
                db_conversation = session.query(DBUserConversation).filter(
                    and_(
                        DBUserConversation.user_id == user_id,
                        DBUserConversation.is_active == True
                    )
                ).order_by(desc(DBUserConversation.updated_at)).first()
            else:
                db_conversation = session.query(DBUserConversation).filter(
                    DBUserConversation.conversation_id == conversation_id
                ).first()
            
            if db_conversation:
                return self._db_to_pydantic_conversation(db_conversation)
            
            return None
    
    async def create_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> UserConversation:
        """Create a new conversation for a user."""
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
        
        with self.db_manager.get_session() as session:
            with session.begin():
                db_conversation = DBUserConversation(
                    user_id=user_id,
                    conversation_id=conversation_id
                )
                
                session.add(db_conversation)
                session.commit()
                
                # Refresh to get the ID and relationships
                session.refresh(db_conversation)
                
                return self._db_to_pydantic_conversation(db_conversation)
    
    async def save_conversation(self, conversation: UserConversation) -> None:
        """Save conversation to database."""
        with self.db_manager.get_session() as session:
            with session.begin():
                db_conversation = session.query(DBUserConversation).filter(
                    DBUserConversation.conversation_id == conversation.conversation_id
                ).first()
                
                if not db_conversation:
                    # Create new conversation
                    db_conversation = self._pydantic_to_db_conversation(conversation)
                    session.add(db_conversation)
                    session.flush()  # Get the ID
                else:
                    # Update existing conversation
                    db_conversation = self._pydantic_to_db_conversation(conversation, db_conversation)
                
                # Handle messages - simple approach: delete and recreate for now
                # In production, you might want more sophisticated sync logic
                session.query(DBConversationMessage).filter(
                    DBConversationMessage.conversation_db_id == db_conversation.id
                ).delete()
                
                for message in conversation.messages:
                    db_message = DBConversationMessage(
                        message_id=message.id,
                        conversation_db_id=db_conversation.id,
                        role=message.role.value,
                        content=message.content,
                        timestamp=message.timestamp,
                        message_metadata=message.metadata
                    )
                    session.add(db_message)
                
                # Handle summaries
                session.query(DBConversationSummary).filter(
                    DBConversationSummary.conversation_db_id == db_conversation.id
                ).delete()
                
                for summary in conversation.summaries:
                    db_summary = DBConversationSummary(
                        conversation_db_id=db_conversation.id,
                        summary=summary.summary,
                        key_topics=summary.key_topics,
                        created_at=summary.created_at,
                        message_count=summary.message_count
                    )
                    session.add(db_summary)
                
                session.commit()
    
    async def list_conversations(self, user_id: str, limit: int = 10, offset: int = 0) -> List[UserConversation]:
        """List conversations for a user."""
        with self.db_manager.get_session() as session:
            db_conversations = session.query(DBUserConversation).filter(
                DBUserConversation.user_id == user_id
            ).order_by(desc(DBUserConversation.updated_at)).limit(limit).offset(offset).all()
            
            return [self._db_to_pydantic_conversation(db_conv) for db_conv in db_conversations]
    
    async def archive_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Archive (mark inactive) a conversation."""
        with self.db_manager.get_session() as session:
            with session.begin():
                db_conversation = session.query(DBUserConversation).filter(
                    and_(
                        DBUserConversation.user_id == user_id,
                        DBUserConversation.conversation_id == conversation_id
                    )
                ).first()
                
                if db_conversation:
                    db_conversation.is_active = False
                    db_conversation.updated_at = datetime.utcnow()
                    session.commit()
                    return True
                
                return False
    
    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Delete a conversation permanently."""
        with self.db_manager.get_session() as session:
            with session.begin():
                db_conversation = session.query(DBUserConversation).filter(
                    and_(
                        DBUserConversation.user_id == user_id,
                        DBUserConversation.conversation_id == conversation_id
                    )
                ).first()
                
                if db_conversation:
                    session.delete(db_conversation)  # Cascade will delete messages and summaries
                    session.commit()
                    return True
                
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
        # Get or create conversation
        conversation = await self.get_conversation(user_id, conversation_id)
        if not conversation:
            conversation = await self.create_conversation(user_id, conversation_id)
        
        # Add message
        message = conversation.add_message(role, content, metadata)
        
        # Save conversation
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
        with self.db_manager.get_session() as session:
            # Get conversation counts
            total_conversations = session.query(DBUserConversation).filter(
                DBUserConversation.user_id == user_id
            ).count()
            
            active_conversations = session.query(DBUserConversation).filter(
                and_(
                    DBUserConversation.user_id == user_id,
                    DBUserConversation.is_active == True
                )
            ).count()
            
            # Get message count
            total_messages = session.query(func.count(DBConversationMessage.id)).join(
                DBUserConversation
            ).filter(DBUserConversation.user_id == user_id).scalar() or 0
            
            # Get last activity
            last_conversation = session.query(DBUserConversation).filter(
                DBUserConversation.user_id == user_id
            ).order_by(desc(DBUserConversation.updated_at)).first()
            
            last_activity = last_conversation.updated_at if last_conversation else None
            avg_messages = total_messages / total_conversations if total_conversations > 0 else 0.0
            
            return ConversationStats(
                user_id=user_id,
                total_conversations=total_conversations,
                total_messages=total_messages,
                active_conversations=active_conversations,
                last_activity=last_activity,
                avg_messages_per_conversation=avg_messages
            )
    
    async def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old conversation data."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with self.db_manager.get_session() as session:
            with session.begin():
                # Find old inactive conversations
                old_conversations = session.query(DBUserConversation).filter(
                    and_(
                        DBUserConversation.updated_at < cutoff_date,
                        DBUserConversation.is_active == False
                    )
                ).all()
                
                cleanup_count = len(old_conversations)
                
                for conversation in old_conversations:
                    session.delete(conversation)  # Cascade will delete messages and summaries
                
                session.commit()
                
                logger.info(f"Cleaned up {cleanup_count} old conversations")
                return cleanup_count
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on persistence backend."""
        return self.db_manager.health_check()
