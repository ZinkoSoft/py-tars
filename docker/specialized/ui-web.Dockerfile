# Stage 1: Build frontend with Node.js
FROM node:20-alpine AS frontend-builder

WORKDIR /workspace/frontend

# Copy frontend package files
COPY apps/ui-web/frontend/package*.json ./

# Install frontend dependencies
RUN npm ci --no-audit --no-fund

# Copy frontend source
COPY apps/ui-web/frontend/ ./

# Build frontend for production
RUN npm run build

# Stage 2: Python runtime with built frontend
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG SERVICE_PATH=apps/ui-web

WORKDIR /app

# Copy tars-core first (dependency of ui-web)
COPY packages/tars-core /app/packages/tars-core

# Copy backend package configuration and source code
COPY ${SERVICE_PATH}/pyproject.toml ./
COPY ${SERVICE_PATH}/src ./src

# Copy built frontend from builder stage
COPY --from=frontend-builder /workspace/frontend/dist ./frontend/dist

# Install tars-core first, then the package
RUN pip install --no-cache-dir -e /app/packages/tars-core && \
    pip install --no-cache-dir -e .

ENV MQTT_URL="mqtt://tars:pass@127.0.0.1:1883"

# Use the installed CLI command
CMD ["tars-ui-web"]
