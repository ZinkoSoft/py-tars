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

# ========== MCP Bridge: Build-Time Discovery & Configuration ==========
# Install mcp-bridge temporarily to discover and configure MCP servers
COPY apps/mcp-bridge /tmp/mcp-bridge
RUN pip install --no-cache-dir /tmp/mcp-bridge

# Copy all MCP server sources for discovery
COPY packages /tmp/workspace/packages
COPY extensions/mcp-servers /tmp/workspace/extensions/mcp-servers
COPY ops/mcp/mcp.server.yml /tmp/workspace/ops/mcp/mcp.server.yml

# Run mcp-bridge to discover, install, and generate config
# This is a ONE-SHOT build-time operation that creates mcp-servers.json
RUN mkdir -p /app/config && \
    cd /tmp/workspace && \
    WORKSPACE_ROOT=/tmp/workspace \
    MCP_LOCAL_PACKAGES_PATH=/tmp/workspace/packages \
    MCP_EXTENSIONS_PATH=/tmp/workspace/extensions/mcp-servers \
    MCP_SERVERS_YAML=/tmp/workspace/ops/mcp/mcp.server.yml \
    MCP_OUTPUT_DIR=/tmp/workspace/config \
    python -m mcp_bridge.main

# The generated config file is now at /tmp/workspace/config/mcp-servers.json
# Copy it to the image for runtime use
RUN cp /tmp/workspace/config/mcp-servers.json /app/config/mcp-servers.json

# Clean up mcp-bridge (no longer needed at runtime)
RUN pip uninstall -y tars-mcp-bridge && \
    rm -rf /tmp/mcp-bridge /tmp/workspace

# Verify config was generated (fail build if missing)
RUN test -f /app/config/mcp-servers.json || (echo "ERROR: mcp-servers.json not generated!" && exit 1)

# ========== End MCP Bridge ==========

# Install LLM worker dependencies ONLY (cached unless pyproject.toml changes)
COPY apps/llm-worker/pyproject.toml /tmp/llm-worker/pyproject.toml
COPY apps/llm-worker/README.md /tmp/llm-worker/README.md
# Create empty package structure for pip install to work
RUN mkdir -p /tmp/llm-worker/llm_worker/providers && \
    touch /tmp/llm-worker/llm_worker/__init__.py && \
    touch /tmp/llm-worker/llm_worker/providers/__init__.py
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir /tmp/llm-worker && \
    rm -rf /tmp/llm-worker

# Source code will be provided via volume mount at /workspace/apps/llm-worker
# This enables live code updates without container rebuild
# NOTE: The pip install above creates the package entry but source comes from workspace

# MCP server configuration is baked into the image at /app/config/mcp-servers.json
# llm-worker will read this at runtime to connect to MCP servers

ENV LOG_LEVEL=INFO \
    MCP_CONFIG_FILE=/app/config/mcp-servers.json

CMD ["python", "-m", "llm_worker"]
