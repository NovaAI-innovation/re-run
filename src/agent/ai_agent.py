"""Pydantic AI agent implementation with Gemini LLM integration."""

import asyncio
import logging
import os
from typing import Optional

from pydantic_ai import Agent
# Google model is initialized using string format in latest Pydantic AI

from src.config.settings import Settings
from src.persistence.manager import ConversationManager
from src.persistence.factory import PersistenceFactory


logger = logging.getLogger(__name__)


class AIAgent:
    """AI agent powered by Pydantic AI and Gemini LLM."""

    def __init__(self, settings: Settings):
        """Initialize the AI agent.

        Args:
            settings: Application configuration settings
        """
        self.settings = settings
        self.agent: Optional[Agent] = None
        self.conversation_manager: Optional[ConversationManager] = None
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the Pydantic AI agent with Gemini model."""
        try:
            logger.info("Initializing AI agent with Gemini model...")

            # Ensure the Google API key is set in environment
            # Pydantic AI expects GOOGLE_API_KEY environment variable
            os.environ['GOOGLE_API_KEY'] = self.settings.google_api_key

            # Create the agent with model string format (latest Pydantic AI approach)
            self.agent = Agent(
                model=self.settings.gemini_model,  # e.g., 'google-gla:gemini-1.5-flash'
                system_prompt=self._create_enhanced_system_prompt()
            )
            
            # Initialize conversation persistence
            storage = PersistenceFactory.create_storage(self.settings)
            self.conversation_manager = ConversationManager(storage, self.settings)
            await self.conversation_manager.initialize()

            self.initialized = True
            logger.info("AI agent initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize AI agent: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown the AI agent gracefully (fully async)."""
        try:
            if self.conversation_manager:
                await self.conversation_manager.shutdown()
                
            if self.agent:
                # Clean up agent resources if needed
                self.agent = None
                
            self.initialized = False
            logger.info("AI agent shutdown complete")
        except Exception as e:
            logger.error(f"Error during AI agent shutdown: {e}")

    async def generate_response(self, message: str, user_id: Optional[str] = None) -> str:
        """Generate a response to a user message.

        Args:
            message: The user's message
            user_id: Optional user identifier for context

        Returns:
            AI-generated response

        Raises:
            RuntimeError: If agent is not initialized
            Exception: For other generation errors
        """
        if not self.initialized or not self.agent:
            raise RuntimeError("AI agent not initialized")

        try:
            logger.debug(f"Generating response for message: {message[:100]}...")
            
            # Add user message to conversation history
            if user_id and self.conversation_manager:
                await self.conversation_manager.add_user_message(user_id, message)

            # Build context-aware prompt
            context_prompt = await self._build_context_prompt(message, user_id)

            # Generate response using Pydantic AI
            result = await self.agent.run(context_prompt)

            # Extract the response content
            response = result.output

            # Truncate if too long
            if len(response) > self.settings.max_response_length:
                response = response[:self.settings.max_response_length - 3] + "..."
                logger.warning(f"Response truncated to {self.settings.max_response_length} characters")
            
            # Add assistant response to conversation history
            if user_id and self.conversation_manager:
                await self.conversation_manager.add_assistant_message(user_id, response)
                
                # Check if conversation should be summarized
                if await self.conversation_manager.should_summarize_conversation(user_id):
                    asyncio.create_task(self._create_conversation_summary(user_id))

            logger.debug(f"Generated response: {response[:100]}...")
            return response

        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            # Return a fallback response
            return "I'm sorry, I encountered an error while processing your message. Please try again later."



    def is_ready(self) -> bool:
        """Check if the agent is ready to process requests."""
        return self.initialized and self.agent is not None
    
    def _create_enhanced_system_prompt(self) -> str:
        """Create an enhanced system prompt that includes conversation context handling."""
        base_prompt = self.settings.system_prompt
        
        enhanced_prompt = f"""{base_prompt}

You have access to conversation history and context. Use this context to provide more personalized and relevant responses. When you see conversation history or summaries in the context, reference previous topics naturally when appropriate.

If you notice the conversation has been going on for a while, occasionally acknowledge the ongoing conversation or reference earlier topics to maintain continuity.

Be conversational and remember that you're having an ongoing dialogue with the user, not just answering isolated questions."""
        
        return enhanced_prompt
    
    async def _build_context_prompt(self, message: str, user_id: Optional[str]) -> str:
        """Build a context-aware prompt including conversation history."""
        if not user_id or not self.conversation_manager:
            return f"User: {message}"
        
        # Get conversation context
        context_messages = await self.conversation_manager.get_conversation_context(user_id)
        
        if not context_messages:
            return f"User: {message}"
        
        # Build conversation history string
        context_parts = []
        
        for ctx_msg in context_messages[-self.settings.context_window_size:]:  # Limit context size
            if ctx_msg.role.value == "system":
                context_parts.append(f"[Summary: {ctx_msg.content}]")
            elif ctx_msg.role.value == "user":
                context_parts.append(f"User: {ctx_msg.content}")
            elif ctx_msg.role.value == "assistant":
                context_parts.append(f"Assistant: {ctx_msg.content}")
        
        # Add current message
        context_parts.append(f"User: {message}")
        
        return "\n\n".join(context_parts)
    
    async def _create_conversation_summary(self, user_id: str) -> None:
        """Create a conversation summary in the background."""
        try:
            if not self.conversation_manager:
                return
                
            # Get conversation context for summarization
            context_messages = await self.conversation_manager.get_conversation_context(user_id)
            
            if not context_messages:
                return
            
            # Build conversation text for summarization
            conversation_text = "\n".join([
                f"{msg.role.value}: {msg.content}" 
                for msg in context_messages 
                if msg.role.value != "system"
            ])
            
            # Generate summary using the AI agent
            summary_prompt = f"""Please create a brief summary of the following conversation, highlighting the key topics and important points discussed:

{conversation_text}

Provide a concise summary (2-3 sentences) and list the main topics discussed."""
            
            result = await self.agent.run(summary_prompt)
            summary_text = result.output
            
            # Extract key topics (simple approach - could be enhanced)
            key_topics = self._extract_key_topics(summary_text)
            
            # Save summary
            await self.conversation_manager.create_conversation_summary(
                user_id=user_id,
                summary=summary_text,
                key_topics=key_topics
            )
            
            logger.info(f"Created conversation summary for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to create conversation summary for {user_id}: {e}")
    
    def _extract_key_topics(self, summary_text: str) -> list[str]:
        """Extract key topics from summary text (simple implementation)."""
        # This is a simple implementation - could be enhanced with NLP techniques
        topics = []
        
        # Look for topic indicators
        lines = summary_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                topic = line.lstrip('-•* ').strip()
                if topic:
                    topics.append(topic)
        
        # If no bullet points found, try to extract from sentences
        if not topics and summary_text:
            # Simple keyword extraction - could be improved
            words = summary_text.lower().split()
            important_words = [word for word in words if len(word) > 4 and word.isalpha()]
            topics = important_words[:5]  # Take first 5 important words as topics
        
        return topics[:10]  # Limit to 10 topics
