# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies (needed for compilation of some python libs like asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (The Astral package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency definitions first (for caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
# --frozen: strict usage of lockfile
# --no-install-project: only install dependencies, not the app code yet
RUN uv sync --frozen --no-install-project

# Copy the rest of the application code
COPY . .

# Install the project itself
RUN uv sync --frozen

# Environment variables for Python
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Default command (can be overridden by docker-compose)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]