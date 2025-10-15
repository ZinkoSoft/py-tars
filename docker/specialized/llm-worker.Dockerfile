# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies (cached layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install tars-core first (cached unless tars-core changes)
COPY packages/tars-core/pyproject.toml packages/tars-core/README.md /tmp/tars-core/
COPY packages/tars-core/src /tmp/tars-core/src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Install tars-mcp-character (MCP server for personality adjustments)
# Pure MCP server with no MQTT dependencies - v0.1.1
COPY packages/tars-mcp-character /tmp/tars-mcp-character
RUN pip install --no-cache-dir /tmp/tars-mcp-character && \
    rm -rf /tmp/tars-mcp-character

# Note: MCP configuration is handled at runtime via volume-mounted config
# The mcp-servers.json will be provided via /workspace/config volume mount
# This allows dynamic MCP server configuration without rebuilding the container

# Install LLM worker dependencies ONLY (cached unless pyproject.toml changes)
COPY apps/llm-worker/pyproject.toml /tmp/llm-worker/pyproject.toml
COPY apps/llm-worker/README.md /tmp/llm-worker/README.md
# Create empty package structure for pip install to work (src/ layout)
RUN mkdir -p /tmp/llm-worker/src/llm_worker/providers /tmp/llm-worker/src/llm_worker/handlers && \
    touch /tmp/llm-worker/src/llm_worker/__init__.py && \
    touch /tmp/llm-worker/src/llm_worker/providers/__init__.py && \
    touch /tmp/llm-worker/src/llm_worker/handlers/__init__.py
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir /tmp/llm-worker && \
    rm -rf /tmp/llm-worker

# Source code will be provided via volume mount at /workspace/apps/llm-worker
# This enables live code updates without container rebuild
# NOTE: The pip install above creates the package entry but source comes from workspace
# The package uses src/ layout, so PYTHONPATH needs to include /workspace/apps/llm-worker/src
ENV PYTHONPATH="/workspace/apps/llm-worker/src:${PYTHONPATH}"

# MCP server configuration expected at runtime via volume mount
# Default path: /workspace/config/mcp-servers.json

ENV LOG_LEVEL=INFO \
    MCP_CONFIG_FILE=/workspace/config/mcp-servers.json

CMD ["python", "-m", "llm_worker"]
