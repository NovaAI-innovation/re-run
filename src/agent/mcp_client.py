"""Model Context Protocol client implementation with pydantic-ai best practices."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, field_validator
from pydantic_ai.mcp import (
    MCPServerStdio,
    CallToolFunc,
    ToolResult
)
from pydantic_ai.tools import RunContext

from src.config.settings import Settings


logger = logging.getLogger(__name__)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server matching Claude desktop config format."""
    
    name: str = Field(..., description="Unique name for this MCP server")
    command: str = Field(..., description="Command to run for the MCP server")
    args: List[str] = Field(default_factory=list, description="Arguments for the command")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    
    # Optional pydantic-ai specific extensions
    tool_prefix: Optional[str] = Field(None, description="Prefix for tool names to avoid conflicts")
    allow_sampling: bool = Field(True, description="Whether to allow MCP sampling")
    enabled: bool = Field(True, description="Whether this server is enabled")
    
    @field_validator("command")
    @classmethod 
    def validate_command(cls, v):
        """Validate command is provided."""
        if not v or not v.strip():
            raise ValueError("Command is required for MCP server")
        return v.strip()


@dataclass
class MCPClientDependencies:
    """Dependencies injected into MCP tool calls."""
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    settings: Optional[Settings] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MCPClient:
    """Model Context Protocol client with pydantic-ai integration."""
    
    def __init__(self, settings: Settings):
        """Initialize the MCP client.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        self.servers: Dict[str, MCPServerStdio] = {}
        self.server_configs: Dict[str, MCPServerConfig] = {}
        self.initialized = False
        
    async def initialize(self, server_configs: List[MCPServerConfig]) -> None:
        """Initialize MCP servers asynchronously.
        
        Args:
            server_configs: List of server configurations
        """
        try:
            logger.info("Initializing MCP client with %d server configs", len(server_configs))
            
            for config in server_configs:
                if not config.enabled:
                    logger.info(f"Skipping disabled MCP server: {config.name}")
                    continue
                    
                await self._create_server(config)
                self.server_configs[config.name] = config
            
            self.initialized = True
            logger.info("MCP client initialized successfully with %d servers", len(self.servers))
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            raise
    
    async def _create_server(self, config: MCPServerConfig) -> None:
        """Create an MCP stdio server instance based on configuration.
        
        Args:
            config: Server configuration
        """
        try:
            server = await self._create_stdio_server(config)
            
            if server:
                self.servers[config.name] = server
                logger.info(f"Created MCP stdio server: {config.name}")
                
        except Exception as e:
            logger.error(f"Failed to create MCP server {config.name}: {e}")
            raise
            
    async def _create_stdio_server(self, config: MCPServerConfig) -> MCPServerStdio:
        """Create a stdio MCP server with enhanced configuration.
        
        Args:
            config: Server configuration
            
        Returns:
            MCPServerStdio instance
        """
        # Auto-generate tool prefix if not provided to avoid conflicts
        tool_prefix = config.tool_prefix or f"{config.name}_"
        
        server = MCPServerStdio(
            command=config.command,
            args=config.args,
            env=config.env,
            tool_prefix=tool_prefix,
            allow_sampling=config.allow_sampling,
            process_tool_call=self._create_tool_call_processor(config.name)
        )
        return server
    
    def _create_tool_call_processor(self, server_name: str) -> CallToolFunc:
        """Create a tool call processor for dependency injection.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Tool call processor function
        """
        async def process_tool_call(
            ctx: RunContext[MCPClientDependencies],
            call_tool: CallToolFunc,
            name: str,
            tool_args: Dict[str, Any],
        ) -> ToolResult:
            """Process tool calls with enhanced dependency injection and error handling."""
            import time
            start_time = time.time()
            
            try:
                # Inject comprehensive dependencies into tool call
                enhanced_args = tool_args.copy()
                
                if ctx.deps:
                    deps_dict = {
                        'user_id': ctx.deps.user_id,
                        'conversation_id': ctx.deps.conversation_id,
                        'server_name': server_name,
                        'metadata': ctx.deps.metadata,
                        'settings': ctx.deps.settings.model_dump() if ctx.deps.settings else {},
                        'timestamp': time.time()
                    }
                    enhanced_args['deps'] = deps_dict
                    
                logger.debug(f"Calling MCP tool {name} on server {server_name} with args: {list(tool_args.keys())}")
                result = await call_tool(name, enhanced_args)
                
                execution_time = time.time() - start_time
                logger.debug(f"MCP tool {name} completed in {execution_time:.2f}s")
                
                return result
                
            except TimeoutError as e:
                logger.error(f"Timeout in MCP tool call {name} on server {server_name}: {e}")
                raise
            except ConnectionError as e:
                logger.error(f"Connection error in MCP tool call {name} on server {server_name}: {e}")
                raise
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Error in MCP tool call {name} on server {server_name} after {execution_time:.2f}s: {e}")
                raise
                
        return process_tool_call
    
    def get_toolsets(self) -> List[MCPServerStdio]:
        """Get all MCP servers as toolsets for pydantic-ai Agent.
        
        Returns:
            List of MCP server instances
        """
        if not self.initialized:
            logger.warning("MCP client not initialized, returning empty toolsets")
            return []
            
        return list(self.servers.values())
    
    async def discover_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Discover all available tools from connected MCP servers.
        
        Returns:
            Dictionary mapping server names to lists of tool information
        """
        if not self.initialized:
            logger.warning("MCP client not initialized, cannot discover tools")
            return {}
        
        tools_by_server = {}
        
        for server_name, server in self.servers.items():
            try:
                # Get tools from the server if it supports tool listing
                if hasattr(server, 'list_tools'):
                    tools = await server.list_tools()
                    tools_by_server[server_name] = [
                        {
                            'name': tool.name,
                            'description': tool.description,
                            'schema': tool.input_schema if hasattr(tool, 'input_schema') else None
                        }
                        for tool in tools
                    ]
                    logger.debug(f"Discovered {len(tools)} tools from server {server_name}")
                else:
                    # If server doesn't support tool listing, note it
                    tools_by_server[server_name] = []
                    logger.debug(f"Server {server_name} doesn't support tool discovery")
                    
            except Exception as e:
                logger.error(f"Failed to discover tools from server {server_name}: {e}")
                tools_by_server[server_name] = []
        
        return tools_by_server
    
    async def get_available_tools_summary(self) -> str:
        """Get a human-readable summary of available tools.
        
        Returns:
            String description of available tools
        """
        if not self.initialized:
            return "MCP client not initialized - no tools available."
        
        tools_by_server = await self.discover_tools()
        
        if not tools_by_server:
            return "No MCP servers connected - no tools available."
        
        summary_parts = []
        total_tools = 0
        
        for server_name, tools in tools_by_server.items():
            if tools:
                summary_parts.append(f"\n{server_name} ({len(tools)} tools):")
                for tool in tools:
                    summary_parts.append(f"  - {tool['name']}: {tool['description']}")
                    total_tools += 1
            else:
                summary_parts.append(f"\n{server_name}: No tools discovered")
        
        if total_tools == 0:
            return f"Connected to {len(tools_by_server)} MCP server(s) but no tools discovered."
        
        header = f"Available MCP Tools ({total_tools} total):"
        return header + "".join(summary_parts)
    
    def get_server_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about connected MCP servers.
        
        Returns:
            Dictionary with server information
        """
        if not self.initialized:
            return {}
        
        server_info = {}
        for name, server in self.servers.items():
            config = self.server_configs.get(name)
            server_info[name] = {
                'name': name,
                'command': config.command if config else 'Unknown',
                'args': config.args if config else [],
                'enabled': config.enabled if config else True,
                'tool_prefix': config.tool_prefix if config else None
            }
        
        return server_info
    
    def get_server(self, name: str) -> Optional[MCPServerStdio]:
        """Get a specific MCP server by name.
        
        Args:
            name: Server name
            
        Returns:
            MCP server instance or None if not found
        """
        return self.servers.get(name)
    
    async def set_sampling_model(self, model_name: Optional[str] = None) -> None:
        """Set sampling model on all MCP servers.
        
        Args:
            model_name: Model name to use for sampling
        """
        try:
            for server_name, server in self.servers.items():
                if hasattr(server, 'sampling_model'):
                    server.sampling_model = model_name
                    logger.info(f"Set sampling model {model_name} on server {server_name}")
                    
        except Exception as e:
            logger.error(f"Failed to set sampling model: {e}")
            raise
    
    async def shutdown(self) -> None:
        """Shutdown all MCP servers gracefully."""
        try:
            logger.info("Shutting down MCP client...")
            
            # Close all server connections
            for server_name, server in self.servers.items():
                try:
                    if hasattr(server, '__aexit__'):
                        await server.__aexit__(None, None, None)
                    logger.debug(f"Closed MCP server: {server_name}")
                except Exception as e:
                    logger.error(f"Error closing MCP server {server_name}: {e}")
            
            self.servers.clear()
            self.server_configs.clear()
            self.initialized = False
            
            logger.info("MCP client shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during MCP client shutdown: {e}")
            
    def __repr__(self) -> str:
        """String representation of MCP client."""
        server_count = len(self.servers)
        server_names = list(self.servers.keys())
        return f"MCPClient(servers={server_count}, names={server_names}, initialized={self.initialized})"
