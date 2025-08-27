#!/bin/bash
# Permission setup script for Docker volumes

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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

# Docker container user ID (from Dockerfile)
DOCKER_UID=10001
DOCKER_GID=10001

# Function to create directories with proper permissions
setup_directories() {
    log_info "Setting up directories for Docker volumes..."
    
    cd "$PROJECT_DIR"
    
    # Create directories if they don't exist
    mkdir -p data/conversations
    mkdir -p logs
    mkdir -p config
    
    log_info "Directories created"
    
    # Check current permissions
    log_info "Current permissions:"
    ls -la data/ logs/ config/ 2>/dev/null || true
    
    # Detect OS and handle permissions accordingly
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        setup_linux_permissions
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        setup_macos_permissions
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        setup_windows_permissions
    else
        log_warn "Unknown OS type: $OSTYPE"
        log_info "Setting basic permissions..."
        chmod -R 755 data logs config 2>/dev/null || true
    fi
}

# Linux permissions setup
setup_linux_permissions() {
    log_info "Setting up permissions for Linux..."
    
    if command -v id &> /dev/null; then
        CURRENT_UID=$(id -u)
        CURRENT_GID=$(id -g)
        
        if [ "$CURRENT_UID" -eq 0 ]; then
            log_info "Running as root, setting proper ownership..."
            chown -R $DOCKER_UID:$DOCKER_GID data logs config
        else
            log_info "Running as user $CURRENT_UID, setting permissions..."
            chmod -R 755 data logs config
            
            # If user can sudo, offer to set proper ownership
            if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
                log_info "Setting ownership using sudo..."
                sudo chown -R $DOCKER_UID:$DOCKER_GID data logs config
            else
                log_warn "Cannot set ownership to Docker user ($DOCKER_UID:$DOCKER_GID)"
                log_warn "Docker container may have permission issues"
                log_info "To fix this, run as root or with sudo:"
                log_info "  sudo chown -R $DOCKER_UID:$DOCKER_GID data logs config"
            fi
        fi
    fi
}

# macOS permissions setup
setup_macos_permissions() {
    log_info "Setting up permissions for macOS..."
    
    # macOS Docker Desktop handles user mapping automatically for most cases
    chmod -R 755 data logs config
    
    log_info "macOS permissions set. Docker Desktop should handle user mapping automatically."
}

# Windows permissions setup
setup_windows_permissions() {
    log_info "Setting up permissions for Windows..."
    
    # Windows with Docker Desktop handles permissions differently
    # Just ensure directories are readable/writable
    if command -v icacls &> /dev/null; then
        icacls data /grant Users:F /T 2>/dev/null || true
        icacls logs /grant Users:F /T 2>/dev/null || true
        icacls config /grant Users:F /T 2>/dev/null || true
    fi
    
    log_info "Windows permissions set. Docker Desktop should handle the rest."
}

# Function to verify permissions
verify_permissions() {
    log_info "Verifying permissions..."
    
    local errors=0
    
    # Check if directories are readable
    for dir in data logs config; do
        if [ ! -r "$dir" ]; then
            log_error "Directory $dir is not readable"
            errors=$((errors + 1))
        fi
        
        if [ ! -w "$dir" ]; then
            log_error "Directory $dir is not writable"
            errors=$((errors + 1))
        fi
    done
    
    if [ $errors -eq 0 ]; then
        log_info "Permission verification passed"
    else
        log_warn "Found $errors permission issues"
        return 1
    fi
}

# Function to test with Docker
test_with_docker() {
    if command -v docker &> /dev/null; then
        log_info "Testing permissions with Docker..."
        
        # Try to run a test container
        if docker run --rm \
            -v "$(pwd)/data:/app/data" \
            -v "$(pwd)/logs:/app/logs" \
            -v "$(pwd)/config:/app/config" \
            --user $DOCKER_UID:$DOCKER_GID \
            alpine:latest \
            sh -c "touch /app/data/test.txt && echo 'Permission test successful' && rm /app/data/test.txt" 2>/dev/null; then
            log_info "Docker permission test passed"
        else
            log_warn "Docker permission test failed"
            log_info "The container may still work, but with warnings"
        fi
    else
        log_warn "Docker not found, skipping Docker test"
    fi
}

# Main function
main() {
    log_info "Docker Volume Permission Setup"
    log_info "=============================="
    
    setup_directories
    
    if verify_permissions; then
        log_info "Basic permission setup completed"
        
        if [ "$TEST_DOCKER" = "true" ]; then
            test_with_docker
        fi
        
        log_info ""
        log_info "Setup completed! You can now run your Docker container:"
        log_info "  docker compose up -d"
        log_info ""
    else
        log_error "Permission setup failed"
        log_error "You may need to run this script with elevated privileges"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --test-docker)
            TEST_DOCKER="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --test-docker    Run Docker permission test"
            echo "  --help          Show this help message"
            echo ""
            echo "This script sets up proper permissions for Docker volume mounts."
            echo "It creates the necessary directories and sets appropriate ownership/permissions."
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
TEST_DOCKER=${TEST_DOCKER:-false}

# Run main function
main
