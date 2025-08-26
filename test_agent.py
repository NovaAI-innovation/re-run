"""Simple test script for the AI agent."""

import asyncio
import os

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

from src.config.settings import Settings
from src.agent.ai_agent import AIAgent


async def test_agent():
    """Test the AI agent with a simple message."""
    try:
        # Create settings (will load from environment)
        settings = Settings()

        # Initialize AI agent
        agent = AIAgent(settings)
        await agent.initialize()

        # Test message
        test_message = "Hello! Can you tell me what the capital of France is?"
        print(f"Test message: {test_message}")

        # Generate response
        response = await agent.generate_response(test_message)
        print(f"AI Response: {response}")

        # Cleanup
        await agent.shutdown()
        print("Test completed successfully!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_agent())
