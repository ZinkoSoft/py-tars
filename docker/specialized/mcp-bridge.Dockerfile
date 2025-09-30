FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY packages/tars-core /tmp/tars-core
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Install the bridge as a wheel to match the centralized build flow
COPY apps/mcp-bridge/pyproject.toml /tmp/mcp-bridge/pyproject.toml
COPY apps/mcp-bridge/README.md /tmp/mcp-bridge/README.md
COPY apps/mcp-bridge/mcp_bridge /tmp/mcp-bridge/mcp_bridge
RUN pip install --no-cache-dir /tmp/mcp-bridge && \
    rm -rf /tmp/mcp-bridge

ENV LOG_LEVEL=INFO

CMD ["python", "-m", "mcp_bridge.main"]