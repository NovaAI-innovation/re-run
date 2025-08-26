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
from src.agent.mcp_client import MCPClient, MCPClientDependencies
from src.agent.mcp_config import MCPConfigManager


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
        self.mcp_client: Optional[MCPClient] = None
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the Pydantic AI agent with Gemini model and MCP client."""
        try:
            logger.info("Initializing AI agent with Gemini model...")

            # Ensure the Google API key is set in environment
            # Pydantic AI expects GOOGLE_API_KEY environment variable
            os.environ['GOOGLE_API_KEY'] = self.settings.google_api_key

            # Initialize MCP client if enabled
            toolsets = []
            if self.settings.mcp_enabled:
                await self._initialize_mcp_client()
                if self.mcp_client:
                    toolsets.extend(self.mcp_client.get_toolsets())

            # Create the agent with optimized model configuration and fallback
            from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
            from pydantic_ai.models.fallback import FallbackModel
            from pydantic_ai.settings import ModelSettings
            
            # Configure primary model with optimized settings
            primary_model = GoogleModel(
                model_name=self.settings.gemini_model.replace('google-gla:', ''),
                settings=GoogleModelSettings(
                    temperature=0.7,  # Balanced creativity
                    max_tokens=self.settings.max_response_length,
                    google_thinking_config={'thinking_budget': 2048} if self.settings.enable_thinking else None,
                )
            )
            
            # Create fallback model for reliability
            fallback_models = [primary_model]
            if self.settings.fallback_model_enabled:
                # Add fallback model (e.g., OpenAI GPT-4o-mini for reliability)
                from pydantic_ai.models.openai import OpenAIModel
                fallback_model = OpenAIModel(
                    'gpt-4o-mini',
                    settings=ModelSettings(
                        temperature=0.5,  # More conservative for fallback
                        max_tokens=self.settings.max_response_length,
                    )
                )
                fallback_models.append(fallback_model)
            
            # Use FallbackModel if multiple models configured
            model = FallbackModel(*fallback_models) if len(fallback_models) > 1 else primary_model
            
            # Create enhanced system prompt with MCP tool awareness
            system_prompt = await self._create_enhanced_system_prompt()
            
            self.agent = Agent(
                model=model,
                system_prompt=system_prompt,
                deps_type=MCPClientDependencies,
                toolsets=toolsets,
                retries=2  # Built-in retry mechanism
            )
            
            # Add self-awareness tools for MCP capabilities
            self._register_self_awareness_tools()
            
            # Set MCP sampling model if enabled
            if self.mcp_client and self.settings.mcp_sampling_enabled:
                self.agent.set_mcp_sampling_model()
            
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
                
            if self.mcp_client:
                await self.mcp_client.shutdown()
                
            if self.agent:
                # Clean up agent resources if needed
                self.agent = None
                
            self.initialized = False
            logger.info("AI agent shutdown complete")
        except Exception as e:
            logger.error(f"Error during AI agent shutdown: {e}")

    async def _initialize_mcp_client(self) -> None:
        """Initialize the MCP client with configured servers."""
        try:
            logger.info("Initializing MCP client...")
            
            self.mcp_client = MCPClient(self.settings)
            
            # Load MCP server configurations
            server_configs = []
            if self.settings.mcp_servers_config:
                # Load from file or JSON string
                try:
                    if self.settings.mcp_servers_config.startswith('{'):
                        # JSON string
                        server_configs = MCPConfigManager.load_from_string(self.settings.mcp_servers_config)
                    else:
                        # File path
                        server_configs = MCPConfigManager.load_from_file(self.settings.mcp_servers_config)
                except Exception as e:
                    logger.warning(f"Failed to load MCP config from settings: {e}")
                    logger.info("Using default MCP configuration")
                    server_configs = MCPConfigManager.get_default_config()
            else:
                # Use default config
                logger.info("No MCP config specified, using default")
                server_configs = MCPConfigManager.get_default_config()
            
            # Validate configurations
            validation_errors = MCPConfigManager.validate_config(server_configs)
            if validation_errors:
                logger.error(f"MCP configuration validation errors: {validation_errors}")
                # Use only valid configs or fallback
                server_configs = [config for config in server_configs if config.enabled]
                if not server_configs:
                    logger.warning("No valid MCP configs found, disabling MCP")
                    self.mcp_client = None
                    return
            
            # Initialize MCP client with server configs
            await self.mcp_client.initialize(server_configs)
            logger.info(f"MCP client initialized with {len(server_configs)} servers")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            self.mcp_client = None

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

            # Create MCP dependencies for tool calls
            deps = MCPClientDependencies(
                user_id=user_id,
                conversation_id=user_id,  # Using user_id as conversation_id for simplicity
                settings=self.settings,
                metadata={"original_message": message}
            )

            # Configure usage limits for responsible AI usage
            from pydantic_ai.usage import UsageLimits
            usage_limits = UsageLimits(
                response_tokens_limit=self.settings.max_response_length,
                request_limit=self.settings.max_requests_per_minute
            )
            
            # Generate response using Pydantic AI with proper context management
            if self.mcp_client and self.mcp_client.get_toolsets():
                async with self.agent:
                    result = await self.agent.run(
                        context_prompt, 
                        deps=deps, 
                        usage_limits=usage_limits
                    )
            else:
                result = await self.agent.run(
                    context_prompt, 
                    usage_limits=usage_limits
                )

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
            from pydantic_ai.exceptions import UsageLimitExceeded, UnexpectedModelBehavior
            
            if isinstance(e, UsageLimitExceeded):
                logger.warning(f"Usage limit exceeded for user {user_id}: {e}")
                return "I apologize, but I've reached my usage limits. Please try a shorter message or try again later."
            elif isinstance(e, UnexpectedModelBehavior):
                logger.warning(f"Model safety triggered for user {user_id}: {e}")
                return "I can't process that request due to content safety guidelines. Please try rephrasing your message."
            else:
                logger.error(f"Failed to generate response for user {user_id}: {e}", exc_info=True)
                return "I'm sorry, I encountered an error while processing your message. Please try again later."



    def is_ready(self) -> bool:
        """Check if the agent is ready to process requests."""
        return self.initialized and self.agent is not None
    
    async def get_available_tools(self) -> dict:
        """Get information about available tools from MCP servers.
        
        Returns:
            Dictionary containing tool information organized by server
        """
        if not self.initialized or not self.mcp_client:
            return {
                "status": "unavailable",
                "message": "MCP client not initialized or not available",
                "servers": {},
                "tools": {}
            }
        
        try:
            # Get tools organized by server
            tools_by_server = await self.mcp_client.discover_tools()
            server_info = self.mcp_client.get_server_info()
            tools_summary = await self.mcp_client.get_available_tools_summary()
            
            # Count total tools
            total_tools = sum(len(tools) for tools in tools_by_server.values())
            
            return {
                "status": "available",
                "message": f"Found {total_tools} tools across {len(server_info)} servers",
                "servers": server_info,
                "tools": tools_by_server,
                "summary": tools_summary
            }
            
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            return {
                "status": "error",
                "message": f"Failed to retrieve tool information: {e}",
                "servers": self.mcp_client.get_server_info() if self.mcp_client else {},
                "tools": {}
            }
    
    async def list_mcp_capabilities(self) -> str:
        """Get a human-readable description of MCP capabilities.
        
        Returns:
            String description of current MCP setup and available tools
        """
        if not self.initialized:
            return "AI agent not initialized."
        
        if not self.mcp_client:
            return "No MCP client configured. MCP tools are not available."
        
        try:
            tools_info = await self.get_available_tools()
            
            if tools_info["status"] == "available":
                return f"""MCP Integration Status: Active

{tools_info['summary']}

Server Details:
""" + "\n".join([
                    f"- {name}: Running {info['command']} (enabled: {info['enabled']})"
                    for name, info in tools_info["servers"].items()
                ]) + f"""

Total Tools Available: {sum(len(tools) for tools in tools_info['tools'].values())}

The agent can use these tools to enhance responses with external capabilities."""
            
            elif tools_info["status"] == "unavailable":
                return f"MCP Integration Status: Not Available\n\nReason: {tools_info['message']}"
            
            else:
                return f"MCP Integration Status: Error\n\nDetails: {tools_info['message']}\n\nConnected servers: {len(tools_info['servers'])}"
                
        except Exception as e:
            logger.error(f"Failed to list MCP capabilities: {e}")
            return f"MCP Integration Status: Error\n\nFailed to retrieve capability information: {e}"
    
    async def _create_enhanced_system_prompt(self) -> str:
        """Create an enhanced system prompt that includes conversation context handling and MCP tool awareness."""
        base_prompt = self.settings.system_prompt
        
        # Get MCP tools information if available
        mcp_tools_info = ""
        if self.mcp_client:
            try:
                tools_summary = await self.mcp_client.get_available_tools_summary()
                server_info = self.mcp_client.get_server_info()
                
                if tools_summary != "MCP client not initialized - no tools available.":
                    mcp_tools_info = f"""

## Available Tools and Capabilities

You have access to external tools through Model Context Protocol (MCP) servers:

{tools_summary}

**Connected Servers:**
"""
                    for server_name, info in server_info.items():
                        mcp_tools_info += f"- **{server_name}**: {info['command']} {' '.join(info['args'])}\n"
                    
                    mcp_tools_info += """
**Tool Usage Guidelines:**
- Use tools when they can help provide more accurate, up-to-date, or comprehensive information
- Consider which tools are most appropriate for the user's request
- Don't hesitate to use multiple tools if needed to complete a task
- Always explain what you're doing when using tools to help the user understand
"""
            except Exception as e:
                logger.warning(f"Failed to get MCP tools info for system prompt: {e}")
                if server_info:
                    mcp_tools_info = f"\n\nYou have access to external tools through {len(server_info)} MCP server(s), but tool discovery failed. You can still attempt to use tools as needed."
        
        enhanced_prompt = f"""{base_prompt}

You have access to conversation history and context. Use this context to provide more personalized and relevant responses. When you see conversation history or summaries in the context, reference previous topics naturally when appropriate.

If you notice the conversation has been going on for a while, occasionally acknowledge the ongoing conversation or reference earlier topics to maintain continuity.

Be conversational and remember that you're having an ongoing dialogue with the user, not just answering isolated questions.{mcp_tools_info}"""
        
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
            # Handle both enum and string role values for backward compatibility
            role_value = ctx_msg.role.value if hasattr(ctx_msg.role, 'value') else str(ctx_msg.role)
            
            if role_value == "system":
                context_parts.append(f"[Summary: {ctx_msg.content}]")
            elif role_value == "user":
                context_parts.append(f"User: {ctx_msg.content}")
            elif role_value == "assistant":
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
                f"{msg.role.value if hasattr(msg.role, 'value') else str(msg.role)}: {msg.content}" 
                for msg in context_messages 
                if (msg.role.value if hasattr(msg.role, 'value') else str(msg.role)) != "system"
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
    
    def _register_self_awareness_tools(self) -> None:
        """Register tools that allow the agent to be aware of its own capabilities."""
        if not self.agent:
            return
        
        from pydantic_ai.tools import Tool
        from pydantic_ai import RunContext
        
        @self.agent.tool
        async def list_available_tools(ctx: RunContext[MCPClientDependencies]) -> str:
            """List all available MCP tools and their capabilities. Use this when a user asks what you can do or what tools are available."""
            if not self.initialized or not self.mcp_client:
                return "No MCP tools are currently available. The agent is operating with basic conversational capabilities only."
            
            try:
                tools_info = await self.get_available_tools()
                
                if tools_info["status"] == "available":
                    response = f"## Available Tools and Capabilities\n\n{tools_info['summary']}\n\n"
                    
                    if tools_info["tools"]:
                        response += "**Detailed Tool List:**\n"
                        for server_name, tools in tools_info["tools"].items():
                            if tools:
                                response += f"\n**{server_name} Tools:**\n"
                                for tool in tools:
                                    response += f"- **{tool['name']}**: {tool['description']}\n"
                            else:
                                response += f"\n**{server_name}**: No tools discovered (server may not support tool listing)\n"
                    
                    return response
                else:
                    return f"Tool discovery failed: {tools_info['message']}"
                    
            except Exception as e:
                logger.error(f"Error in list_available_tools: {e}")
                return f"Failed to retrieve tool information: {e}"
        
        @self.agent.tool  
        async def get_mcp_status(ctx: RunContext[MCPClientDependencies]) -> str:
            """Get the current status of MCP (Model Context Protocol) integration. Use this to check if external tools are working properly."""
            return await self.list_mcp_capabilities()
        
        logger.info("Registered self-awareness tools for MCP capabilities")
