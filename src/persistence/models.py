"""Data models for conversation persistence using Pydantic."""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


class MessageRole(str, Enum):
    """Message role enumeration."""
    USER = "user"
    ASSISTANT = "assistant" 
    SYSTEM = "system"


class ConversationMessage(BaseModel):
    """Individual message in a conversation with enhanced validation."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        },
        validate_assignment=True,  # Validate on assignment
        use_enum_values=False     # Keep enum objects for consistency
    )
    
    id: str = Field(..., description="Unique message identifier", min_length=1)
    role: MessageRole = Field(..., description="Role of the message sender")
    content: str = Field(..., description="Message content", min_length=1, max_length=50000)
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate message content."""
        if not v.strip():
            raise ValueError("Message content cannot be empty or whitespace only")
        return v.strip()
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamp is not in the future."""
        if v > datetime.utcnow():
            raise ValueError("Message timestamp cannot be in the future")
        return v


class ConversationSummary(BaseModel):
    """Summary of conversation for efficient context management."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    summary: str = Field(..., description="AI-generated summary of conversation")
    key_topics: List[str] = Field(default_factory=list, description="Key topics discussed")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Summary creation timestamp")
    message_count: int = Field(..., description="Number of messages summarized")


class UserConversation(BaseModel):
    """Complete conversation history for a user."""
    
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    user_id: str = Field(..., description="Unique user identifier")
    conversation_id: str = Field(..., description="Unique conversation identifier")  
    messages: List[ConversationMessage] = Field(default_factory=list, description="All messages in conversation")
    summaries: List[ConversationSummary] = Field(default_factory=list, description="Conversation summaries for context")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Conversation start timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    is_active: bool = Field(default=True, description="Whether conversation is active")
    context_window_size: int = Field(default=10, description="Number of recent messages to include in context")
    
    def get_recent_context(self, include_summary: bool = True) -> List[ConversationMessage]:
        """Get recent messages for context with optional summary."""
        context_messages = []
        
        # Add latest summary as system message for context
        if include_summary and self.summaries:
            latest_summary = max(self.summaries, key=lambda s: s.created_at)
            summary_message = ConversationMessage(
                id=f"summary_{latest_summary.created_at.isoformat()}",
                role=MessageRole.SYSTEM,
                content=f"Previous conversation summary: {latest_summary.summary}",
                timestamp=latest_summary.created_at
            )
            context_messages.append(summary_message)
        
        # Add recent messages
        recent_messages = self.messages[-self.context_window_size:] if self.messages else []
        context_messages.extend(recent_messages)
        
        return context_messages
    
    def add_message(self, role: MessageRole, content: str, metadata: Optional[Dict[str, Any]] = None) -> ConversationMessage:
        """Add a new message to the conversation."""
        import uuid
        
        message = ConversationMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            metadata=metadata or {}
        )
        
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
        
        return message
    
    def should_summarize(self, max_messages: int = 50) -> bool:
        """Check if conversation should be summarized."""
        if len(self.messages) < max_messages:
            return False
            
        # Check if we haven't summarized recently
        if not self.summaries:
            return True
            
        latest_summary = max(self.summaries, key=lambda s: s.created_at)
        messages_since_summary = len([
            msg for msg in self.messages 
            if msg.timestamp > latest_summary.created_at
        ])
        
        return messages_since_summary >= max_messages // 2


class ConversationStats(BaseModel):
    """Statistics about user conversations."""
    
    user_id: str = Field(..., description="User identifier")
    total_conversations: int = Field(default=0, description="Total number of conversations")
    total_messages: int = Field(default=0, description="Total number of messages")
    active_conversations: int = Field(default=0, description="Number of active conversations")
    last_activity: Optional[datetime] = Field(default=None, description="Last conversation activity")
    avg_messages_per_conversation: float = Field(default=0.0, description="Average messages per conversation")
