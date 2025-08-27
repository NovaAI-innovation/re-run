#!/bin/bash
# Build script for the Async Telegram Bot Docker image

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
IMAGE_NAME="async-telegram-bot"
PYTHON_VERSION="3.12"

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
    
    # Check if we're in the right directory
    if [ ! -f "$PROJECT_DIR/Dockerfile" ]; then
        log_error "Dockerfile not found. Are you in the correct directory?"
        exit 1
    fi
    
    if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
        log_error "requirements.txt not found"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Function to build the Docker image
build_image() {
    log_info "Building Docker image: $IMAGE_NAME"
    
    cd "$PROJECT_DIR"
    
    # Build the image
    if docker build \
        --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
        --tag "$IMAGE_NAME:latest" \
        --tag "$IMAGE_NAME:$(date +%Y%m%d)" \
        --progress=plain \
        .; then
        log_info "Docker image built successfully"
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
}

# Function to show image information
show_image_info() {
    log_info "Docker image information:"
    
    # Show image details
    docker images "$IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}"
    
    # Show image layers (if requested)
    if [ "$VERBOSE" = "true" ]; then
        log_info "Image layers:"
        docker history "$IMAGE_NAME:latest" --format "table {{.CreatedBy}}\t{{.Size}}"
    fi
}

# Function to run basic tests
run_tests() {
    log_info "Running basic container tests..."
    
    # Test if container starts without errors
    if docker run --rm --entrypoint="" "$IMAGE_NAME:latest" python3 --version; then
        log_info "Python version test passed"
    else
        log_error "Python version test failed"
        exit 1
    fi
    
    # Test if application files are present
    if docker run --rm --entrypoint="" "$IMAGE_NAME:latest" ls -la /app/main.py > /dev/null 2>&1; then
        log_info "Application files test passed"
    else
        log_error "Application files test failed"
        exit 1
    fi
    
    # Test entrypoint script
    if docker run --rm --entrypoint="" "$IMAGE_NAME:latest" test -x /app/docker-entrypoint.sh; then
        log_info "Entrypoint script test passed"
    else
        log_error "Entrypoint script test failed"
        exit 1
    fi
    
    log_info "Basic tests completed successfully"
}

# Function to clean up old images
cleanup() {
    if [ "$CLEANUP" = "true" ]; then
        log_info "Cleaning up old images..."
        
        # Remove dangling images
        if docker images -f "dangling=true" -q | xargs -r docker rmi; then
            log_info "Removed dangling images"
        fi
        
        # Remove old tagged images (keep last 3)
        OLD_IMAGES=$(docker images "$IMAGE_NAME" --format "{{.ID}}" | tail -n +4)
        if [ -n "$OLD_IMAGES" ]; then
            echo "$OLD_IMAGES" | xargs -r docker rmi
            log_info "Removed old tagged images"
        fi
    fi
}

# Main function
main() {
    log_info "Starting Docker build process..."
    
    check_prerequisites
    build_image
    show_image_info
    
    if [ "$RUN_TESTS" = "true" ]; then
        run_tests
    fi
    
    cleanup
    
    log_info "Build process completed successfully!"
    log_info "To run the container:"
    log_info "  docker compose up -d"
    log_info "Or:"
    log_info "  docker run -d --env-file docker.env -v \$(pwd)/data:/app/data $IMAGE_NAME:latest"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --python-version)
            PYTHON_VERSION="$2"
            shift 2
            ;;
        --image-name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="true"
            shift
            ;;
        --no-tests)
            RUN_TESTS="false"
            shift
            ;;
        --cleanup)
            CLEANUP="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --python-version VERSION  Python version to use (default: 3.12)"
            echo "  --image-name NAME         Docker image name (default: async-telegram-bot)"
            echo "  --verbose                 Show detailed information"
            echo "  --no-tests               Skip running tests"
            echo "  --cleanup                Clean up old images"
            echo "  --help                   Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set defaults
RUN_TESTS=${RUN_TESTS:-true}
CLEANUP=${CLEANUP:-false}
VERBOSE=${VERBOSE:-false}

# Run main function
main
