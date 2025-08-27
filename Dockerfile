# syntax=docker/dockerfile:1

# Use Python 3.12 slim image as base for better security and smaller size
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim AS base

# Install uv and uvx by copying from official image (best practice)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering
ENV PYTHONUNBUFFERED=1

# Ensure Node.js, npm, uv, and uvx are in PATH for all users
ENV PATH="/usr/local/bin:$PATH"

# Set working directory
WORKDIR /app

# Create a non-privileged user that the app will run under
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/bin/bash" \
    --uid "${UID}" \
    appuser

# Install system dependencies including Node.js for MCP servers
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @modelcontextprotocol/server-filesystem

# Download dependencies as a separate step to take advantage of Docker's caching
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds
# Leverage a bind mount to requirements.txt to avoid having to copy them into this layer
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install --no-cache-dir -r requirements.txt

# Create necessary directories and ensure proper ownership
RUN mkdir -p /app/data/conversations /app/logs /home/appuser && \
    chown -R appuser:appuser /app /home/appuser

# Switch to the non-privileged user to run the application
USER appuser

# Copy the source code into the container
COPY --chown=appuser:appuser . .

# Create a health check script
RUN echo '#!/bin/bash\ntest -f /app/bot.log && echo "App is running" || exit 1' > /app/healthcheck.sh && \
    chmod +x /app/healthcheck.sh

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ["/app/healthcheck.sh"]

# Expose port if needed (though this app doesn't use HTTP by default)
# EXPOSE 8000

# Copy the entrypoint script
COPY --chown=appuser:appuser docker-entrypoint.sh /app/docker-entrypoint.sh

# Make entrypoint script executable  
USER root
RUN chmod +x /app/docker-entrypoint.sh
USER appuser

# Set the entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Run the application
CMD ["python3", "main.py"]
