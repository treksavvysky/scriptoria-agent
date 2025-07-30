# Docker Testing Guide for Scriptoria Agent

This guide provides multiple ways to test Scriptoria Agent using Docker containers.

## Quick Start

### 1. Basic Testing
Run the automated test suite:
```bash
./test-docker.sh
```

### 2. Manual Docker Commands

#### Build the image:
```bash
docker build -t scriptoria-agent:latest .
```

#### Run tests:
```bash
docker run --rm scriptoria-agent:latest
```

#### Run demo script:
```bash
docker run --rm -v "$(pwd)/docker_demo.py:/app/docker_demo.py" scriptoria-agent:latest python docker_demo.py
```

## Using Docker Compose

### Available Services

1. **scriptoria-test**: Runs the test suite
2. **scriptoria-dev**: Development container (stays running)
3. **scriptoria-interactive**: Interactive Python shell

### Commands

```bash
# Run tests
docker-compose up scriptoria-test

# Start development container
docker-compose up -d scriptoria-dev

# Interactive Python session
docker-compose run --rm scriptoria-interactive

# Execute commands in running dev container
docker exec -it scriptoria-agent-dev python3
docker exec -it scriptoria-agent-dev bash

# View logs
docker-compose logs scriptoria-dev

# Stop all containers
docker-compose down
```

## Testing Different Python Versions

Build and test against multiple Python versions:

```bash
# Python 3.9
docker build -f Dockerfile.multi-python --target python39 -t scriptoria-agent:py39 .
docker run --rm scriptoria-agent:py39

# Python 3.10
docker build -f Dockerfile.multi-python --target python310 -t scriptoria-agent:py310 .
docker run --rm scriptoria-agent:py310

# Python 3.11
docker build -f Dockerfile.multi-python --target python311 -t scriptoria-agent:py311 .
docker run --rm scriptoria-agent:py311

# Python 3.12
docker build -f Dockerfile.multi-python --target python312 -t scriptoria-agent:py312 .
docker run --rm scriptoria-agent:py312
```

## Interactive Development

1. Start the development container:
   ```bash
   docker-compose up -d scriptoria-dev
   ```

2. Access Python shell:
   ```bash
   docker exec -it scriptoria-agent-dev python3
   ```

3. Test FileManager:
   ```python
   from scriptoria.file_manager import FileManager
   import pathlib
   
   # Create FileManager instance
   fm = FileManager(pathlib.Path("/app/workspace"))
   
   # Test operations
   fm.write("test.txt", "Hello from Docker!")
   content = fm.read("test.txt")
   print(content)
   
   # List files
   files = fm.list_dir(".")
   print(files)
   ```

## Volume Persistence

The Docker setup includes a persistent volume (`scriptoria-workspace`) that maintains files between container restarts. This allows you to:

- Test file persistence
- Debug file operations
- Maintain test data across sessions

## Environment Variables

- `PYTHONPATH=/app`: Ensures proper module imports
- `SCRIPTORIA_WORKSPACE=/app/workspace`: Default workspace location

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure Docker has proper permissions
2. **Port conflicts**: Stop other containers using same ports
3. **Build failures**: Check internet connection for package downloads

### Cleanup

Remove all containers and volumes:
```bash
docker-compose down -v
docker rmi scriptoria-agent:latest
```

### Logs

View container logs:
```bash
docker-compose logs -f scriptoria-dev
```

## Integration Testing

The Docker setup is perfect for:

- **CI/CD testing**: Use in GitHub Actions or other CI systems
- **Environment isolation**: Test without affecting your host system
- **Multi-Python testing**: Verify compatibility across Python versions
- **Deployment simulation**: Test how your agent behaves in containerized environments
