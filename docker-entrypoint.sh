#!/bin/bash
# Docker entrypoint script for the Async Telegram Bot

set -e

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ENTRYPOINT] $1"
}

# Function to check if required environment variables are set
check_required_env() {
    local missing_vars=()
    
    if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
        missing_vars+=("TELEGRAM_BOT_TOKEN")
    fi
    
    if [ -z "$GOOGLE_API_KEY" ]; then
        missing_vars+=("GOOGLE_API_KEY")
    fi
    
    if [ ${#missing_vars[@]} -gt 0 ]; then
        log "ERROR: Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            log "  - $var"
        done
        log "Please set these variables in your docker.env file or docker-compose.yml"
        exit 1
    fi
}

# Function to create necessary directories
create_directories() {
    log "Creating necessary directories..."
    mkdir -p /app/data/conversations
    mkdir -p /app/logs
    mkdir -p /app/config
    
    # Try to set proper permissions (may fail on mounted volumes, which is OK)
    chmod 755 /app/data /app/logs /app/config 2>/dev/null || log "WARNING: Could not change permissions on mounted volumes (this is normal)"
    chmod 755 /app/data/conversations 2>/dev/null || true
    
    # Check if directories are writable
    if [ -w "/app/data" ] && [ -w "/app/logs" ]; then
        log "Data and log directories are writable"
    else
        log "WARNING: Some directories may not be writable. Check host directory permissions."
    fi
}

# Function to validate configuration
validate_config() {
    log "Validating configuration..."
    
    # Check if MCP is enabled and config exists
    if [ "$MCP_ENABLED" = "true" ]; then
        if [ ! -f "/app/$MCP_SERVERS_CONFIG" ]; then
            log "WARNING: MCP is enabled but config file not found at $MCP_SERVERS_CONFIG"
            log "Creating empty MCP configuration..."
            echo '{"mcpServers": {}}' > "/app/$MCP_SERVERS_CONFIG"
        fi
    fi
    
    # Validate persistence type
    if [ "$PERSISTENCE_TYPE" != "json" ] && [ "$PERSISTENCE_TYPE" != "database" ]; then
        log "WARNING: Invalid PERSISTENCE_TYPE '$PERSISTENCE_TYPE'. Defaulting to 'json'"
        export PERSISTENCE_TYPE=json
    fi
    
    # Check database URL if using database persistence
    if [ "$PERSISTENCE_TYPE" = "database" ] && [ -z "$DATABASE_URL" ]; then
        log "WARNING: PERSISTENCE_TYPE is 'database' but DATABASE_URL is not set. Defaulting to SQLite."
        export DATABASE_URL="sqlite:///data/conversations.db"
    fi
}

# Function to wait for external services (if any)
wait_for_services() {
    # Add any service waiting logic here if needed
    # For example, waiting for a database to be ready
    log "Checking external service dependencies..."
    
    if [[ "$DATABASE_URL" == postgresql* ]]; then
        log "PostgreSQL database detected. You may want to add connection checking logic here."
    fi
}

# Function to run database migrations or setup (if needed)
setup_database() {
    if [ "$PERSISTENCE_TYPE" = "database" ]; then
        log "Setting up database..."
        # Add any database initialization logic here
        python3 -c "
from src.persistence.database import DatabaseStorage
from src.config.settings import Settings
import asyncio

async def init_db():
    settings = Settings()
    if settings.persistence_enabled and settings.persistence_type == 'database':
        storage = DatabaseStorage(settings.database_url)
        await storage.initialize()
        print('Database initialized successfully')

asyncio.run(init_db())
" 2>/dev/null || log "Database initialization skipped or failed (this might be normal)"
    fi
}

# Main execution
main() {
    log "Starting Async Telegram Bot container..."
    log "Environment: ${ENVIRONMENT:-development}"
    log "Python version: $(python3 --version)"
    log "Working directory: $(pwd)"
    
    # Run all setup functions
    check_required_env
    create_directories
    validate_config
    wait_for_services
    setup_database
    
    log "Configuration validation complete. Starting application..."
    
    # Execute the main command
    exec "$@"
}

# Run main function with all arguments
main "$@"
