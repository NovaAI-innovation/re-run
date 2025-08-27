#!/bin/bash
# Run script for the Async Telegram Bot Docker container

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
IMAGE_NAME="async-telegram-bot"
CONTAINER_NAME="async-telegram-bot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if image exists
    if ! docker images "$IMAGE_NAME" --format "{{.Repository}}" | grep -q "$IMAGE_NAME"; then
        log_error "Docker image $IMAGE_NAME not found. Please build it first:"
        log_error "  ./docker-scripts/build.sh"
        exit 1
    fi
    
    # Check if docker.env exists
    if [ ! -f "$PROJECT_DIR/docker.env" ]; then
        log_warn "docker.env file not found"
        if [ -f "$PROJECT_DIR/docker.env.example" ]; then
            log_info "Creating docker.env from example..."
            cp "$PROJECT_DIR/docker.env.example" "$PROJECT_DIR/docker.env"
            log_warn "Please edit docker.env and set your API keys before running the container"
        else
            log_error "No environment configuration found"
            exit 1
        fi
    fi
    
    log_info "Prerequisites check passed"
}

# Function to create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p "$PROJECT_DIR/data/conversations"
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/config"
    
    # Set proper permissions (if running as root)
    if [ "$(id -u)" -eq 0 ]; then
        chown -R 10001:10001 "$PROJECT_DIR/data" "$PROJECT_DIR/logs" 2>/dev/null || true
    fi
}

# Function to stop existing container
stop_container() {
    if docker ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Stopping existing container: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME" || true
        docker rm "$CONTAINER_NAME" || true
    fi
}

# Function to run the container
run_container() {
    log_info "Starting container: $CONTAINER_NAME"
    
    cd "$PROJECT_DIR"
    
    # Build docker run command
    DOCKER_CMD=(
        docker run
        --name "$CONTAINER_NAME"
        --env-file docker.env
        --volume "$(pwd)/data:/app/data"
        --volume "$(pwd)/logs:/app/logs"
        --volume "$(pwd)/config:/app/config"
        --restart unless-stopped
    )
    
    # Add detach flag if not in interactive mode
    if [ "$INTERACTIVE" != "true" ]; then
        DOCKER_CMD+=(--detach)
    fi
    
    # Add the image name
    DOCKER_CMD+=("$IMAGE_NAME:latest")
    
    # Run the container
    if "${DOCKER_CMD[@]}"; then
        if [ "$INTERACTIVE" = "true" ]; then
            log_info "Container started in interactive mode"
        else
            log_info "Container started successfully in background"
            log_info "Container ID: $(docker ps --format "{{.ID}}" --filter "name=$CONTAINER_NAME")"
        fi
    else
        log_error "Failed to start container"
        exit 1
    fi
}

# Function to show container status
show_status() {
    log_info "Container status:"
    
    if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "name=$CONTAINER_NAME" | grep -q "$CONTAINER_NAME"; then
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}" --filter "name=$CONTAINER_NAME"
        
        # Show health status if available
        HEALTH=$(docker inspect "$CONTAINER_NAME" --format "{{.State.Health.Status}}" 2>/dev/null || echo "unknown")
        if [ "$HEALTH" != "unknown" ] && [ "$HEALTH" != "<no value>" ]; then
            log_info "Health status: $HEALTH"
        fi
    else
        log_warn "Container is not running"
    fi
}

# Function to show logs
show_logs() {
    if docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
        log_info "Showing container logs (press Ctrl+C to exit):"
        docker logs -f "$CONTAINER_NAME"
    else
        log_error "Container is not running"
        exit 1
    fi
}

# Function to exec into container
exec_container() {
    if docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
        log_info "Executing shell in container..."
        docker exec -it "$CONTAINER_NAME" bash
    else
        log_error "Container is not running"
        exit 1
    fi
}

# Function to stop and remove container
stop_and_remove() {
    log_info "Stopping and removing container: $CONTAINER_NAME"
    
    if docker ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        docker stop "$CONTAINER_NAME" || true
        docker rm "$CONTAINER_NAME" || true
        log_info "Container stopped and removed"
    else
        log_info "Container does not exist"
    fi
}

# Main function
main() {
    case "$COMMAND" in
        start)
            log_info "Starting Async Telegram Bot container..."
            check_prerequisites
            create_directories
            stop_container
            run_container
            show_status
            ;;
        stop)
            stop_and_remove
            ;;
        restart)
            log_info "Restarting container..."
            stop_and_remove
            sleep 2
            check_prerequisites
            create_directories
            run_container
            show_status
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        shell)
            exec_container
            ;;
        *)
            echo "Usage: $0 COMMAND [OPTIONS]"
            echo ""
            echo "Commands:"
            echo "  start     Start the container"
            echo "  stop      Stop and remove the container"
            echo "  restart   Restart the container"
            echo "  status    Show container status"
            echo "  logs      Show and follow container logs"
            echo "  shell     Execute shell in running container"
            echo ""
            echo "Options:"
            echo "  --interactive    Run container in interactive mode (for start command)"
            echo "  --help          Show this help message"
            exit 1
            ;;
    esac
}

# Parse command line arguments
COMMAND=""
while [[ $# -gt 0 ]]; do
    case $1 in
        start|stop|restart|status|logs|shell)
            if [ -z "$COMMAND" ]; then
                COMMAND="$1"
                shift
            else
                log_error "Multiple commands specified"
                exit 1
            fi
            ;;
        --interactive)
            INTERACTIVE="true"
            shift
            ;;
        --help)
            main
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if command was provided
if [ -z "$COMMAND" ]; then
    log_error "No command specified"
    main
fi

# Set defaults
INTERACTIVE=${INTERACTIVE:-false}

# Run main function
main
