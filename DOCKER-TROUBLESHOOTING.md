# Docker Troubleshooting Guide

This guide helps resolve common issues when running the Async Telegram Bot in Docker containers.

## Common Issues and Solutions

### 1. Permission Errors on Volume Mounts

**Symptoms:**
```
chmod: changing permissions of '/app/data': Operation not permitted
chmod: changing permissions of '/app/logs': Operation not permitted
```

**Cause:** 
The Docker container runs as a non-root user (`appuser` with UID 10001), but the mounted volumes from the host may have different ownership.

**Solutions:**

#### Option A: Use the Setup Script (Recommended)
```bash
./docker-scripts/setup-permissions.sh
```

#### Option B: Manual Permission Setup

**Linux/macOS:**
```bash
# Create directories
mkdir -p data/conversations logs config

# Set ownership to match container user
sudo chown -R 10001:10001 data logs config

# Or set broader permissions
chmod -R 755 data logs config
```

**Windows (PowerShell):**
```powershell
# Create directories
New-Item -ItemType Directory -Force data/conversations, logs, config

# Windows with Docker Desktop handles permissions automatically
```

#### Option C: Run Container as Current User
Modify your `compose.yml` to run as your current user:
```yaml
services:
  telegram-bot:
    user: "${UID:-1000}:${GID:-1000}"  # Add this line
    # ... rest of configuration
```

### 2. Container Keeps Restarting

**Check logs:**
```bash
docker compose logs telegram-bot
```

**Common causes:**

#### Missing Environment Variables
**Error:** `ERROR: Missing required environment variables`
**Solution:** 
1. Copy `docker.env.example` to `docker.env`
2. Fill in your API keys:
   ```bash
   TELEGRAM_BOT_TOKEN=your_actual_token_here
   GOOGLE_API_KEY=your_actual_api_key_here
   ```

#### Python Module Import Errors
**Error:** `ModuleNotFoundError: No module named 'src'`
**Solution:** The `PYTHONPATH` is already set in `docker.env`. If issues persist, check the Dockerfile builds correctly.

### 3. Bot Not Responding to Messages

#### Check Bot Token
Verify your Telegram bot token is correct:
```bash
# Test with curl
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

#### Check Container Status
```bash
docker compose ps
docker compose logs -f telegram-bot
```

#### Check Network Connectivity
```bash
# Exec into running container
docker compose exec telegram-bot bash

# Test internet connectivity
ping -c 3 api.telegram.org
```

### 4. Database/Storage Issues

#### SQLite Permission Issues
**Error:** `sqlite3.OperationalError: unable to open database file`
**Solution:**
```bash
# Ensure data directory is writable
chmod 755 data
chmod 644 data/conversations.db  # if file exists
```

#### Switching from JSON to Database
1. Update `docker.env`:
   ```bash
   PERSISTENCE_TYPE=database
   DATABASE_URL=sqlite:///data/conversations.db
   ```
2. Restart container:
   ```bash
   docker compose down
   docker compose up -d
   ```

### 5. MCP (Model Context Protocol) Issues

#### MCP Config File Not Found
**Error:** `WARNING: MCP is enabled but config file not found`
**Solutions:**
1. Disable MCP:
   ```bash
   # In docker.env
   MCP_ENABLED=false
   ```
2. Create config file:
   ```bash
   mkdir -p config
   echo '{"mcpServers": {}}' > config/mcp_servers.json
   ```

### 6. Resource Issues

#### High Memory Usage
```bash
# Check container resource usage
docker stats telegram-bot

# Set memory limits in compose.yml
services:
  telegram-bot:
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
```

#### Disk Space Issues
```bash
# Check disk usage
docker system df

# Clean up unused resources
docker system prune -a
```

## Debugging Commands

### Container Information
```bash
# Container status
docker compose ps

# Container logs
docker compose logs -f telegram-bot

# Container resource usage
docker stats telegram-bot

# Container processes
docker compose exec telegram-bot ps aux
```

### File System Inspection
```bash
# List container files
docker compose exec telegram-bot ls -la /app/

# Check permissions
docker compose exec telegram-bot ls -la /app/data/ /app/logs/

# Check Python environment
docker compose exec telegram-bot python3 -c "import sys; print(sys.path)"
```

### Network Testing
```bash
# Test external connectivity
docker compose exec telegram-bot wget -O - https://api.telegram.org/bot<TOKEN>/getMe

# Check environment variables
docker compose exec telegram-bot env | grep -E "(TELEGRAM|GOOGLE)"
```

### Application Testing
```bash
# Test Python imports
docker compose exec telegram-bot python3 -c "from src.bot.telegram_bot import TelegramBot; print('Import successful')"

# Run health check manually
docker compose exec telegram-bot /app/healthcheck.sh

# Check application logs
docker compose exec telegram-bot cat logs/bot.log
```

## Performance Optimization

### 1. Image Size Optimization
```bash
# Check image layers
docker history async-telegram-bot:latest

# Multi-stage build is already implemented in Dockerfile
```

### 2. Caching Optimization
The Dockerfile already implements:
- Layer caching for pip dependencies
- Cache mounts for pip cache
- Optimized layer ordering

### 3. Runtime Optimization
```yaml
# In compose.yml, add resource limits
services:
  telegram-bot:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

## Security Best Practices

### 1. Environment Variables
```bash
# Never commit real tokens to version control
# Use .env files that are in .gitignore
# For production, use Docker secrets:

echo "your_token_here" | docker secret create telegram_token -
```

### 2. Network Security
```yaml
# Custom network in compose.yml
networks:
  bot-network:
    driver: bridge
    internal: true  # No external access
```

### 3. User Security
The Dockerfile already implements:
- Non-root user (`appuser`)
- Minimal base image (Python slim)
- Health checks

## Production Deployment Checklist

### Pre-deployment
- [ ] API keys properly configured
- [ ] Volume permissions set correctly
- [ ] Resource limits defined
- [ ] Backup strategy in place
- [ ] Monitoring configured

### Post-deployment
- [ ] Health checks passing
- [ ] Logs being generated correctly
- [ ] Bot responding to test messages
- [ ] Data persistence working
- [ ] No permission errors in logs

### Monitoring Commands
```bash
# Health status
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"

# Resource usage over time
watch -n 5 'docker stats --no-stream telegram-bot'

# Log monitoring
docker compose logs -f --tail=100 telegram-bot
```

## Getting Help

### Debug Information Collection
When reporting issues, include:

```bash
# System information
uname -a
docker --version
docker compose --version

# Container information
docker compose ps
docker compose logs --tail=50 telegram-bot

# Image information
docker images async-telegram-bot

# Volume information
ls -la data/ logs/ config/
```

### Support Channels
- Check the main README.md for application-specific issues
- Review Docker documentation for container issues
- Check GitHub issues for known problems

### Emergency Recovery
```bash
# Stop and remove everything
docker compose down -v

# Clean up
docker system prune -a

# Rebuild and restart
./docker-scripts/build.sh
./docker-scripts/setup-permissions.sh
docker compose up -d
```
