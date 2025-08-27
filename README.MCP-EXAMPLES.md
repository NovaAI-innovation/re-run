# MCP Server Configuration Examples

This document provides examples of configuring MCP (Model Context Protocol) servers using both `npx` (Node.js) and `uvx` (Python) commands in the containerized environment.

## Overview

The container now supports both:
- **`npx`**: For running Node.js/JavaScript MCP servers
- **`uvx`**: For running Python MCP servers

## Configuration Format

MCP servers are configured in `config/mcp_servers.json` using the following format:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx|uvx",
      "args": ["arguments", "for", "the", "command"],
      "env": {
        "ENVIRONMENT_VAR": "value"
      }
    }
  }
}
```

## Node.js Examples (using npx)

### Filesystem Server
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/app/data/"
      ]
    }
  }
}
```

### Memory Server
```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ]
    }
  }
}
```

## Python Examples (using uvx)

**Important Note**: `uvx` is available for running Python-based MCP servers, but you need actual MCP server packages, not regular Python tools. Regular Python tools like `ruff`, `black`, etc. are not MCP servers.

### Example Python MCP Server (Hypothetical)
```json
{
  "mcpServers": {
    "python-mcp-server": {
      "command": "uvx",
      "args": [
        "some-python-mcp-server-package",
        "--config",
        "/app/config.json"
      ],
      "env": {
        "PYTHONPATH": "/app"
      }
    }
  }
}
```

**Note**: As of now, most MCP servers are Node.js-based. Python MCP servers are less common, but `uvx` is ready when they become available.

## Mixed Configuration Example

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/app/data/"
      ]
    },
    "memory": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ]
    }
  }
}
```

When Python-based MCP servers become available, you could add them like:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/app/data/"]
    },
    "python-server": {
      "command": "uvx",
      "args": ["python-mcp-server-package"],
      "env": {"PYTHONPATH": "/app"}
    }
  }
}
```

## Best Practices

1. **Use `npx -y`** for Node.js packages to automatically install if not present
2. **Set `PYTHONPATH`** for Python tools that need to access your project code
3. **Use specific versions** when needed: `uvx package@version`
4. **Configure environment variables** for tools that need specific settings
5. **Test configurations** by running commands manually first:
   ```bash
   docker exec -it <container> uvx ruff --version
   docker exec -it <container> npx -y @modelcontextprotocol/server-filesystem --help
   ```

## Available Commands

### In the Container
- **npx**: Node.js package executor (v10.9.3)
- **uvx**: Python package executor (v0.8.13)

### Testing Commands
```bash
# Test npx availability
docker run --rm --entrypoint="" <image> npx --version

# Test uvx availability  
docker run --rm --entrypoint="" <image> uvx --version

# Test running a Python tool
docker run --rm --entrypoint="" <image> uvx ruff --version
```

## Troubleshooting

1. **Command not found**: Ensure the container has been rebuilt after adding uv/uvx
2. **Permission errors**: Check that the user has appropriate permissions
3. **Network issues**: uvx downloads packages from PyPI, ensure internet access
4. **Path issues**: Both commands are installed in `/usr/bin/` and should be in PATH
