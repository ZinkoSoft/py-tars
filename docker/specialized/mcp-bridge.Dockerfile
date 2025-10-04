FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl nodejs npm && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install tars-core first (cached unless tars-core changes)
COPY packages/tars-core/pyproject.toml packages/tars-core/README.md /tmp/tars-core/
COPY packages/tars-core/src /tmp/tars-core/src
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Install built-in MCP servers (tars-mcp-character, etc.)
COPY packages/tars-mcp-character /tmp/tars-mcp-character
RUN pip install --no-cache-dir /tmp/tars-mcp-character && \
    rm -rf /tmp/tars-mcp-character

# Install user extension MCP servers (if any exist)
COPY extensions/mcp-servers /tmp/extensions/mcp-servers
RUN for dir in /tmp/extensions/mcp-servers/*/; do \
      if [ -f "$dir/pyproject.toml" ]; then \
        echo "Installing extension: $(basename $dir)"; \
        pip install --no-cache-dir "$dir"; \
      fi; \
    done && \
    rm -rf /tmp/extensions

# Install mcp-bridge dependencies only (not the package itself)
COPY apps/mcp-bridge/pyproject.toml /tmp/mcp-bridge/pyproject.toml
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('/tmp/mcp-bridge/pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -rf /tmp/mcp-bridge /tmp/requirements.txt

# Source code will be provided via volume mount at /workspace/apps/mcp-bridge
# This enables live code updates without container rebuild

ENV LOG_LEVEL=INFO \
    PYTHONPATH=/app

CMD ["python", "-m", "mcp_bridge.main"]