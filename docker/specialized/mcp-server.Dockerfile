FROM python:3.11-slim

WORKDIR /app

# Install tars-core first (required for contracts)
COPY packages/tars-core /tmp/tars-core
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Copy and install the MCP server package
COPY apps/mcp-server/pyproject.toml /tmp/mcp-server/pyproject.toml
COPY apps/mcp-server/tars_mcp_server /tmp/mcp-server/tars_mcp_server

RUN pip install --no-cache-dir /tmp/mcp-server && \
    rm -rf /tmp/mcp-server

# FastMCP CLI handles stdio/http/sse via command line
# Default to stdio, but compose.yml will override with sse --port 8000
CMD ["tars-mcp-server", "stdio"]
