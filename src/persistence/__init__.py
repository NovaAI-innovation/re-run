"""Persistence module for conversation storage and management."""

from .models import (
    MessageRole,
    ConversationMessage,
    ConversationSummary,
    UserConversation,
    ConversationStats
)

from .interface import ConversationPersistenceInterface
from .json_storage import JsonConversationStorage
from .db_storage import DatabaseConversationStorage
from .manager import ConversationManager
from .factory import PersistenceFactory

__all__ = [
    'MessageRole',
    'ConversationMessage', 
    'ConversationSummary',
    'UserConversation',
    'ConversationStats',
    'ConversationPersistenceInterface',
    'JsonConversationStorage',
    'DatabaseConversationStorage', 
    'ConversationManager',
    'PersistenceFactory'
]
