# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies (git is required for GitManager)
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
# Setup tools to build the package
RUN pip install --no-cache-dir build setuptools

# Copy the entire application code
COPY . .

# Install the application and all dependencies from pyproject.toml
RUN pip install --no-cache-dir .

# Expose the API port
EXPOSE 8080

# Start the FastAPI application via uvicorn
CMD ["sh", "-c", "uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
