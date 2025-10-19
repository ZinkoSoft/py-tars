# Dockerfile for config-manager service
# Based on existing TARS app.Dockerfile pattern

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package dependencies
COPY packages/tars-core /app/packages/tars-core
COPY apps/config-manager /app/apps/config-manager

# Copy configuration metadata
RUN mkdir -p /etc/tars
COPY ops/config-metadata.yml /etc/tars/config-metadata.yml

# Install tars-core package
RUN pip install --no-cache-dir -e /app/packages/tars-core

# Install config-manager package
RUN pip install --no-cache-dir -e /app/apps/config-manager

# Create data directory for database
RUN mkdir -p /data/config

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CONFIG_DB_PATH=/data/config/config.db
ENV CONFIG_LKG_CACHE_PATH=/data/config/config.lkg.json
ENV CONFIG_EPOCH_PATH=/data/config/health+epoch.json

# Expose HTTP port
EXPOSE 8081

# Run the service
CMD ["python", "-m", "config_manager"]
