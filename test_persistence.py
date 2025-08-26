#!/usr/bin/env python3
"""Test script to validate conversation persistence implementation."""

import asyncio
import tempfile
import shutil
from pathlib import Path

from src.persistence import (
    JsonConversationStorage,
    MessageRole,
    ConversationManager,
    PersistenceFactory
)
from src.config.settings import Settings


async def test_json_storage():
    """Test JSON storage implementation."""
    print("🧪 Testing JSON Storage Implementation...")
    
    # Create temporary storage directory
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        storage = JsonConversationStorage(storage_dir=temp_dir)
        await storage.initialize()
        
        user_id = "test_user_123"
        
        # Test adding messages
        print("  ✅ Adding messages...")
        message1 = await storage.add_message(user_id, MessageRole.USER, "Hello, world!")
        message2 = await storage.add_message(user_id, MessageRole.ASSISTANT, "Hi there! How can I help you?")
        message3 = await storage.add_message(user_id, MessageRole.USER, "What's the weather like?")
        
        # Test getting context
        print("  ✅ Retrieving context...")
        context = await storage.get_context_messages(user_id)
        assert len(context) == 3
        assert context[0].role == MessageRole.USER
        assert "Hello, world!" in context[0].content
        
        # Test conversation retrieval
        print("  ✅ Testing conversation retrieval...")
        conversation = await storage.get_conversation(user_id)
        assert conversation is not None
        assert len(conversation.messages) == 3
        
        # Test stats
        print("  ✅ Testing user stats...")
        stats = await storage.get_user_stats(user_id)
        assert stats.total_conversations == 1
        assert stats.total_messages == 3
        
        # Test health check
        print("  ✅ Testing health check...")
        health = await storage.health_check()
        assert health["healthy"] is True
        
        await storage.shutdown()
        print("  ✅ JSON storage tests passed!")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


async def test_conversation_manager():
    """Test conversation manager with mock settings."""
    print("🧪 Testing Conversation Manager...")
    
    # Create mock settings
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        # Create a settings instance with JSON storage
        settings = Settings(
            telegram_bot_token="test_token:123456789",
            google_api_key="test_api_key_123456789012345678901234567890",
            persistence_enabled=True,
            persistence_type="json",
            json_storage_dir=str(temp_dir)
        )
        
        storage = PersistenceFactory.create_storage(settings)
        manager = ConversationManager(storage, settings)
        
        await manager.initialize()
        
        user_id = "test_user_456"
        
        # Test adding messages
        print("  ✅ Adding user message...")
        await manager.add_user_message(user_id, "Hello from manager!")
        
        print("  ✅ Adding assistant message...")  
        await manager.add_assistant_message(user_id, "Hello back from assistant!")
        
        # Test getting context
        print("  ✅ Getting conversation context...")
        context = await manager.get_conversation_context(user_id)
        assert len(context) == 2
        
        # Test stats
        print("  ✅ Getting user stats...")
        stats = await manager.get_user_stats(user_id)
        assert stats is not None
        assert stats.total_messages == 2
        
        # Test health check
        print("  ✅ Health check...")
        health = await manager.health_check()
        assert health["enabled"] is True
        assert health["healthy"] is True
        
        await manager.shutdown()
        print("  ✅ Conversation manager tests passed!")
        
    finally:
        shutil.rmtree(temp_dir)


async def test_persistence_disabled():
    """Test behavior when persistence is disabled."""
    print("🧪 Testing Disabled Persistence...")
    
    settings = Settings(
        telegram_bot_token="test_token:123456789",
        google_api_key="test_api_key_123456789012345678901234567890",
        persistence_enabled=False
    )
    
    storage = PersistenceFactory.create_storage(settings)
    assert storage is None
    
    manager = ConversationManager(storage, settings)
    await manager.initialize()
    
    user_id = "test_user_789"
    
    # All operations should return appropriate values for disabled state
    result = await manager.add_user_message(user_id, "Test message")
    assert result is False
    
    context = await manager.get_conversation_context(user_id)
    assert len(context) == 0
    
    stats = await manager.get_user_stats(user_id)
    assert stats is None
    
    health = await manager.health_check()
    assert health["enabled"] is False
    
    await manager.shutdown()
    print("  ✅ Disabled persistence tests passed!")


async def main():
    """Run all tests."""
    print("🚀 Starting Conversation Persistence Tests\n")
    
    try:
        await test_json_storage()
        print()
        
        await test_conversation_manager()
        print()
        
        await test_persistence_disabled()
        print()
        
        print("🎉 All tests passed! Conversation persistence is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
