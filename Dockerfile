# Dockerfile for Scriptoria Agent
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
COPY setup.py .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY scriptoria/ ./scriptoria/
COPY tests/ ./tests/

# Install the package in development mode
RUN pip install -e .

# Create a workspace directory for testing
RUN mkdir -p /app/workspace

# Set environment variables
ENV PYTHONPATH=/app
ENV SCRIPTORIA_WORKSPACE=/app/workspace

# Default command runs tests
CMD ["python", "-m", "pytest", "tests/", "-v"]
