# Docker Setup for Async Telegram Bot

This guide explains how to run the Async Telegram Bot using Docker containers.

## Quick Start

### 1. Configure Environment Variables

Copy and customize the environment file:

```bash
cp docker.env.example docker.env
```

Edit `docker.env` and set your API keys and configuration:

```bash
# Required: Set your Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Required: Set your Google API Key  
GOOGLE_API_KEY=your_google_api_key_here

# Optional: Customize other settings as needed
```

### 2. Run with Docker Compose (Recommended)

```bash
# Build and start the bot
docker compose up -d

# View logs
docker compose logs -f telegram-bot

# Stop the bot
docker compose down
```

### 3. Run with Docker Commands

```bash
# Build the image
docker build -t async-telegram-bot .

# Run the container
docker run -d \
  --name async-telegram-bot \
  --env-file docker.env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  --restart unless-stopped \
  async-telegram-bot

# View logs
docker logs -f async-telegram-bot

# Stop and remove container
docker stop async-telegram-bot
docker rm async-telegram-bot
```

## Configuration

### Environment Variables

The application uses environment variables for configuration. Key variables include:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | Yes | - |
| `GOOGLE_API_KEY` | Google AI API key | Yes | - |
| `GEMINI_MODEL` | Gemini model to use | No | `google-gla:gemini-1.5-flash` |
| `LOG_LEVEL` | Logging level | No | `INFO` |
| `PERSISTENCE_TYPE` | Storage type (`json` or `database`) | No | `json` |
| `DATABASE_URL` | Database connection string | No | `sqlite:///data/conversations.db` |
| `MCP_ENABLED` | Enable MCP functionality | No | `false` |

### Volume Mounts

The container uses these volume mounts for persistent data:

- `/app/data` - Conversation data and database files
- `/app/logs` - Application log files  
- `/app/config` - Configuration files (MCP servers, etc.)

### Persistence Options

#### JSON Storage (Default)
```env
PERSISTENCE_TYPE=json
JSON_STORAGE_DIR=data/conversations
```

#### Database Storage
```env
PERSISTENCE_TYPE=database
DATABASE_URL=sqlite:///data/conversations.db
# Or for PostgreSQL:
# DATABASE_URL=postgresql://user:password@postgres:5432/telegram_bot
```

## Docker Compose Services

### Main Bot Service
The primary service that runs your Telegram bot.

### Optional Services (commented out by default)

#### PostgreSQL Database
Uncomment the `postgres` service in `compose.yml` to use PostgreSQL:

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: telegram_bot
    POSTGRES_USER: bot_user
    POSTGRES_PASSWORD: your_secure_password
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

Then update your `docker.env`:
```env
PERSISTENCE_TYPE=database
DATABASE_URL=postgresql://bot_user:your_secure_password@postgres:5432/telegram_bot
```

#### Redis Cache
Uncomment the `redis` service for caching functionality:

```yaml
redis:
  image: redis:7-alpine
  volumes:
    - redis_data:/data
```

## Development

### Building the Image

```bash
# Build with default Python version
docker build -t async-telegram-bot .

# Build with specific Python version
docker build --build-arg PYTHON_VERSION=3.11 -t async-telegram-bot .
```

### Running in Development Mode

For development, you can mount the source code:

```bash
docker run -it --rm \
  --env-file docker.env \
  -v $(pwd):/app \
  -v $(pwd)/data:/app/data \
  python:3.12-slim \
  bash -c "cd /app && pip install -r requirements.txt && python main.py"
```

### Debugging

View container logs:
```bash
# All logs
docker compose logs telegram-bot

# Follow logs
docker compose logs -f telegram-bot

# Last 100 lines
docker compose logs --tail=100 telegram-bot
```

Execute commands in running container:
```bash
docker compose exec telegram-bot bash
```

## Health Checks

The container includes health checks that verify the application is running correctly:

```bash
# Check health status
docker compose ps

# Manual health check
docker compose exec telegram-bot /app/healthcheck.sh
```

## Security Considerations

1. **Environment Variables**: Never commit real API keys to version control
2. **User Permissions**: The container runs as a non-root user (`appuser`)
3. **Network**: The bot doesn't expose any ports by default
4. **Volumes**: Use named volumes or secure host directories
5. **Updates**: Regularly update the base image and dependencies

## Troubleshooting

### Common Issues

#### Missing API Keys
```
ERROR: Missing required environment variables: TELEGRAM_BOT_TOKEN
```
Solution: Set the required variables in your `docker.env` file.

#### Permission Issues
```
Permission denied: '/app/data'
```
Solution: Check volume mount permissions or run:
```bash
sudo chown -R 10001:10001 ./data ./logs
```

#### MCP Configuration Not Found
```
WARNING: MCP is enabled but config file not found
```
Solution: Create the MCP config file or disable MCP:
```bash
echo '{"mcpServers": {}}' > config/mcp_servers.json
```

### Logs and Debugging

- Application logs: `./logs/bot.log` (on host) or `/app/logs/bot.log` (in container)
- Container logs: `docker compose logs telegram-bot`
- Health status: `docker compose ps`

### Performance Tuning

For high-volume bots, consider:
- Using PostgreSQL instead of SQLite
- Adding Redis for caching
- Increasing container resource limits
- Using multiple container instances behind a load balancer

## Production Deployment

### Security Hardening
1. Use specific image tags instead of `latest`
2. Run security scans: `docker scan async-telegram-bot`
3. Use secrets management for API keys
4. Enable log rotation
5. Monitor resource usage

### Monitoring
```bash
# Resource usage
docker stats telegram-bot

# System info
docker compose exec telegram-bot cat /proc/meminfo
docker compose exec telegram-bot df -h
```

### Backup
```bash
# Backup data directory
tar -czf telegram-bot-backup-$(date +%Y%m%d).tar.gz data/

# Backup database (if using PostgreSQL)
docker compose exec postgres pg_dump -U bot_user telegram_bot > backup.sql
```

## Support

For issues related to:
- Docker setup: Check this README and Docker documentation
- Application functionality: Check the main README.md
- MCP integration: Check MCP server documentation
