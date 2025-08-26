"""SQLAlchemy database models for conversation persistence."""

from datetime import datetime
from typing import List, Optional, Dict, Any
import json

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.types import TypeDecorator, VARCHAR

Base = declarative_base()


class JSONType(TypeDecorator):
    """Custom SQLAlchemy type for storing JSON data."""
    
    impl = Text
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Process value before storing in database."""
        if value is not None:
            return json.dumps(value)
        return value
    
    def process_result_value(self, value, dialect):
        """Process value after retrieving from database."""
        if value is not None:
            return json.loads(value)
        return value


class DBUserConversation(Base):
    """SQLAlchemy model for user conversations."""
    
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    context_window_size = Column(Integer, default=10, nullable=False)
    
    # Relationships
    messages = relationship("DBConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    summaries = relationship("DBConversationSummary", back_populates="conversation", cascade="all, delete-orphan")


class DBConversationMessage(Base):
    """SQLAlchemy model for conversation messages."""
    
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(255), nullable=False, unique=True, index=True)
    conversation_db_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    message_metadata = Column(JSONType, default=lambda: {})
    
    # Relationships
    conversation = relationship("DBUserConversation", back_populates="messages")


class DBConversationSummary(Base):
    """SQLAlchemy model for conversation summaries."""
    
    __tablename__ = "summaries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_db_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    summary = Column(Text, nullable=False)
    key_topics = Column(JSONType, default=lambda: [])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    message_count = Column(Integer, nullable=False)
    
    # Relationships
    conversation = relationship("DBUserConversation", back_populates="summaries")


class DatabaseManager:
    """Database manager using SQLAlchemy with best practices."""
    
    def __init__(self, database_url: str):
        """
        Initialize database manager.
        
        Args:
            database_url: SQLAlchemy database URL
        """
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
    
    def initialize(self) -> None:
        """Initialize database connection and create tables."""
        try:
            # Create engine with connection pooling for better performance
            self.engine = create_engine(
                self.database_url,
                echo=False,  # Set to True for debugging
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,   # Recycle connections after 1 hour
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize database: {e}")
    
    def get_session(self) -> Session:
        """Get database session using context manager pattern."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()
    
    def shutdown(self) -> None:
        """Shutdown database connections."""
        if self.engine:
            self.engine.dispose()
    
    def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        try:
            with self.get_session() as session:
                # Simple query to test connection
                result = session.execute("SELECT 1").scalar()
                
                # Get basic statistics
                total_conversations = session.query(DBUserConversation).count()
                total_messages = session.query(DBConversationMessage).count()
                active_conversations = session.query(DBUserConversation).filter_by(is_active=True).count()
                
                return {
                    "healthy": True,
                    "database_url": self.database_url,
                    "connection_test": result == 1,
                    "total_conversations": total_conversations,
                    "total_messages": total_messages,
                    "active_conversations": active_conversations,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
