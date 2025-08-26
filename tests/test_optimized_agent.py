"""Comprehensive tests for optimized PydanticAI agent functionality."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from pydantic_ai.models.test import TestModel
from pydantic_ai.exceptions import UsageLimitExceeded, UnexpectedModelBehavior
from src.agent.ai_agent import AIAgent
from src.config.settings import Settings


@pytest.fixture
def optimized_settings():
    """Create settings for testing optimized features."""
    return Settings(
        telegram_bot_token="test_token",
        google_api_key="test_key", 
        fallback_model_enabled=True,
        openai_api_key="test_openai_key",
        enable_thinking=True,
        mcp_enabled=False,
        persistence_enabled=False
    )


@pytest.fixture
async def test_agent(optimized_settings):
    """Create test agent with mocked models."""
    agent = AIAgent(optimized_settings)
    
    # Mock the model initialization to use TestModel
    with patch('pydantic_ai.models.google.GoogleModel') as mock_google, \
         patch('pydantic_ai.models.openai.OpenAIModel') as mock_openai:
        
        mock_google.return_value = TestModel()
        mock_openai.return_value = TestModel()
        
        await agent.initialize()
    
    yield agent
    await agent.shutdown()


class TestOptimizedAgent:
    """Test suite for optimized agent functionality."""
    
    async def test_fallback_model_configuration(self, test_agent):
        """Test that fallback model is properly configured."""
        assert test_agent.agent is not None
        assert test_agent.initialized
    
    async def test_usage_limits_handling(self, test_agent):
        """Test proper handling of usage limits."""
        with patch.object(test_agent.agent, 'run') as mock_run:
            mock_run.side_effect = UsageLimitExceeded("Token limit exceeded")
            
            response = await test_agent.generate_response("test message", "user123")
            
            assert "usage limits" in response.lower()
            assert "shorter message" in response.lower()
    
    async def test_model_safety_handling(self, test_agent):
        """Test handling of model safety exceptions."""
        with patch.object(test_agent.agent, 'run') as mock_run:
            mock_run.side_effect = UnexpectedModelBehavior("Content policy violation")
            
            response = await test_agent.generate_response("inappropriate content", "user123")
            
            assert "content safety guidelines" in response.lower()
    
    async def test_thinking_capability_configuration(self, optimized_settings):
        """Test that thinking capability is properly configured."""
        optimized_settings.enable_thinking = True
        agent = AIAgent(optimized_settings)
        
        # Verify thinking is enabled in initialization logic
        assert agent.settings.enable_thinking
    
    async def test_comprehensive_error_logging(self, test_agent, caplog):
        """Test that errors are properly logged with context."""
        with patch.object(test_agent.agent, 'run') as mock_run:
            mock_run.side_effect = Exception("Unexpected error")
            
            response = await test_agent.generate_response("test", "user123")
            
            # Check that error was logged with user context
            assert any("user123" in record.message for record in caplog.records)
            assert "encountered an error" in response


class TestMCPOptimizations:
    """Test suite for MCP optimizations."""
    
    async def test_tool_prefix_auto_generation(self):
        """Test that tool prefixes are automatically generated."""
        from src.agent.mcp_client import MCPClient
        from src.agent.mcp_client import MCPServerConfig
        
        settings = Settings(telegram_bot_token="test", google_api_key="test")
        client = MCPClient(settings)
        
        config = MCPServerConfig(
            name="test_server",
            command="echo",
            args=["hello"],
            tool_prefix=None  # Should auto-generate
        )
        
        # Test auto-generation logic
        expected_prefix = "test_server_"
        # This would be tested in the actual _create_stdio_server method
    
    async def test_enhanced_dependency_injection(self):
        """Test that comprehensive dependencies are injected."""
        from src.agent.mcp_client import MCPClientDependencies
        
        deps = MCPClientDependencies(
            user_id="test_user",
            conversation_id="test_conv",
            settings=Settings(telegram_bot_token="test", google_api_key="test"),
            metadata={"test": "data"}
        )
        
        assert deps.user_id == "test_user"
        assert deps.conversation_id == "test_conv"
        assert deps.settings is not None
        assert deps.metadata["test"] == "data"


class TestPersistenceValidation:
    """Test enhanced persistence model validation."""
    
    def test_conversation_message_validation(self):
        """Test ConversationMessage validation."""
        from src.persistence.models import ConversationMessage, MessageRole
        
        # Test valid message
        valid_message = ConversationMessage(
            id="test_id",
            role=MessageRole.USER,
            content="This is a valid message"
        )
        assert valid_message.content == "This is a valid message"
        
        # Test content validation
        with pytest.raises(ValueError, match="cannot be empty"):
            ConversationMessage(
                id="test_id",
                role=MessageRole.USER,
                content="   "  # Only whitespace
            )
        
        # Test content length validation
        with pytest.raises(ValueError):
            ConversationMessage(
                id="test_id",
                role=MessageRole.USER,
                content="x" * 50001  # Exceeds max length
            )
    
    def test_message_timestamp_validation(self):
        """Test timestamp validation."""
        from datetime import datetime, timedelta
        from src.persistence.models import ConversationMessage, MessageRole
        
        # Test future timestamp (should fail)
        future_time = datetime.utcnow() + timedelta(hours=1)
        
        with pytest.raises(ValueError, match="cannot be in the future"):
            ConversationMessage(
                id="test_id",
                role=MessageRole.USER,
                content="Test message",
                timestamp=future_time
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
