#!/bin/bash
# Docker testing script for Scriptoria Agent

set -e

echo "🐳 Scriptoria Agent Docker Testing Suite"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    print_warning "docker-compose not found. Using 'docker compose' instead."
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

print_status "Building Scriptoria Agent Docker image..."
docker build -t scriptoria-agent:latest .

print_success "Docker image built successfully!"

# Test 1: Run unit tests
print_status "Running unit tests in Docker container..."
if docker run --rm scriptoria-agent:latest; then
    print_success "Unit tests passed!"
else
    print_error "Unit tests failed!"
    exit 1
fi

# Test 2: Run demo script
print_status "Running demo script..."
docker run --rm -v "$(pwd)/docker_demo.py:/app/docker_demo.py" scriptoria-agent:latest python docker_demo.py

print_success "Demo script completed!"

# Test 3: Interactive testing
print_status "Starting interactive development container..."
echo "You can now test Scriptoria Agent interactively."
echo "The container will be available as 'scriptoria-agent-dev'"
echo ""
echo "Useful commands:"
echo "  docker exec -it scriptoria-agent-dev python3"
echo "  docker exec -it scriptoria-agent-dev bash"
echo "  $DOCKER_COMPOSE down  # to stop the container"
echo ""

$DOCKER_COMPOSE up -d scriptoria-dev

if [ $? -eq 0 ]; then
    print_success "Development container is running!"
    print_status "Container logs:"
    $DOCKER_COMPOSE logs scriptoria-dev
else
    print_error "Failed to start development container"
    exit 1
fi

print_success "All Docker tests completed successfully! 🎉"
echo ""
echo "Next steps:"
echo "1. Run: docker exec -it scriptoria-agent-dev python3"
echo "2. Test: from scriptoria.file_manager import FileManager"
echo "3. Clean up: $DOCKER_COMPOSE down"
