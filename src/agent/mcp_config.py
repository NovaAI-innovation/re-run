"""MCP configuration management and parsing."""

import json
import logging
from pathlib import Path
from typing import List, Optional

from src.agent.mcp_client import MCPServerConfig


logger = logging.getLogger(__name__)


class MCPConfigManager:
    """Manager for MCP server configurations."""
    
    @staticmethod
    def load_from_file(config_path: str) -> List[MCPServerConfig]:
        """Load MCP server configurations from JSON file.
        
        Args:
            config_path: Path to JSON configuration file
            
        Returns:
            List of MCPServerConfig instances
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        try:
            path = Path(config_path)
            if not path.exists():
                raise FileNotFoundError(f"MCP config file not found: {config_path}")
            
            with open(path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return MCPConfigManager._parse_config(config_data)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in MCP config file {config_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to load MCP config from {config_path}: {e}")
            raise
    
    @staticmethod
    def load_from_string(config_json: str) -> List[MCPServerConfig]:
        """Load MCP server configurations from JSON string.
        
        Args:
            config_json: JSON string containing server configurations
            
        Returns:
            List of MCPServerConfig instances
            
        Raises:
            ValueError: If JSON string is invalid
        """
        try:
            config_data = json.loads(config_json)
            return MCPConfigManager._parse_config(config_data)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in MCP config string: {e}")
        except Exception as e:
            logger.error(f"Failed to parse MCP config from string: {e}")
            raise
    
    @staticmethod
    def _parse_config(config_data: dict) -> List[MCPServerConfig]:
        """Parse configuration data into MCPServerConfig instances.
        
        Args:
            config_data: Dictionary containing configuration data in Claude desktop format
            
        Returns:
            List of MCPServerConfig instances
        """
        servers = []
        
        if not isinstance(config_data, dict):
            raise ValueError("MCP config must be a JSON object")
        
        # Support both Claude desktop format and legacy format
        if "mcpServers" in config_data:
            # Claude desktop config format
            mcp_servers = config_data.get("mcpServers", {})
            if not isinstance(mcp_servers, dict):
                raise ValueError("MCP config 'mcpServers' must be an object")
            
            for server_name, server_config in mcp_servers.items():
                try:
                    # Convert Claude format to our internal format
                    server_data = {
                        "name": server_name,
                        "command": server_config.get("command"),
                        "args": server_config.get("args", []),
                        "env": server_config.get("env"),
                        # Default values for pydantic-ai extensions
                        "tool_prefix": None,
                        "allow_sampling": True,
                        "enabled": True
                    }
                    
                    server_config_obj = MCPServerConfig(**server_data)
                    servers.append(server_config_obj)
                    logger.debug(f"Parsed MCP server config: {server_name}")
                    
                except Exception as e:
                    logger.error(f"Invalid MCP server config for '{server_name}': {e}")
                    raise ValueError(f"Invalid MCP server config for '{server_name}': {e}")
        
        elif "servers" in config_data:
            # Legacy array format
            servers_list = config_data.get("servers", [])
            if not isinstance(servers_list, list):
                raise ValueError("MCP config 'servers' must be a list")
            
            for i, server_data in enumerate(servers_list):
                try:
                    server_config = MCPServerConfig(**server_data)
                    servers.append(server_config)
                    logger.debug(f"Parsed MCP server config: {server_config.name}")
                    
                except Exception as e:
                    logger.error(f"Invalid MCP server config at index {i}: {e}")
                    raise ValueError(f"Invalid MCP server config at index {i}: {e}")
        
        else:
            raise ValueError("MCP config must contain either 'mcpServers' (Claude format) or 'servers' (legacy format)")
        
        logger.info(f"Parsed {len(servers)} MCP server configurations")
        return servers
    
    @staticmethod
    def get_default_config() -> List[MCPServerConfig]:
        """Get a default MCP configuration for testing.
        
        Returns:
            List with a default MCP server config for run-python server
        """
        return [
            MCPServerConfig(
                name="run_python",
                command="deno",
                args=[
                    "run",
                    "-N",
                    "-R=node_modules",
                    "-W=node_modules", 
                    "--node-modules-dir=auto",
                    "jsr:@pydantic/mcp-run-python",
                    "stdio"
                ],
                tool_prefix="py",
                allow_sampling=True,
                enabled=True
            )
        ]
    
    @staticmethod
    def save_config_template(output_path: str) -> None:
        """Save an MCP configuration template to a file in Claude desktop format.
        
        Args:
            output_path: Path where to save the template
        """
        try:
            # Use Claude desktop config format
            template = {
                "mcpServers": {
                    "run_python": {
                        "command": "deno",
                        "args": [
                            "run",
                            "-N", 
                            "-R=node_modules",
                            "-W=node_modules",
                            "--node-modules-dir=auto",
                            "jsr:@pydantic/mcp-run-python",
                            "stdio"
                        ]
                    },
                    "brave-search": {
                        "command": "npx",
                        "args": [
                            "-y",
                            "brave-search-mcp"
                        ],
                        "env": {
                            "BRAVE_API_KEY": "your-api-key-here"
                        }
                    },
                    "github-repos-manager": {
                        "command": "npx",
                        "args": [
                            "-y",
                            "github-repos-manager-mcp"
                        ],
                        "env": {
                            "GH_TOKEN": "your-github-token-here"
                        }
                    }
                }
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2)
            
            logger.info(f"Saved MCP configuration template to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save MCP config template: {e}")
            raise
    
    @staticmethod
    def validate_config(config: List[MCPServerConfig]) -> List[str]:
        """Validate MCP server configurations.
        
        Args:
            config: List of MCPServerConfig instances
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        server_names = set()
        
        for i, server in enumerate(config):
            # Check for duplicate names
            if server.name in server_names:
                errors.append(f"Duplicate server name '{server.name}' at index {i}")
            server_names.add(server.name)
            
            # Validate servers have required command (all are stdio in Claude format)
            if not server.command:
                errors.append(f"Server '{server.name}' missing required command")
        
        return errors
