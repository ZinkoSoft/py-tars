FROM python:3.11-slim

WORKDIR /app

# Install tars-core first (required for contracts)
COPY packages/tars-core /tmp/tars-core
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Copy and install the MCP server package
COPY packages/tars-mcp-character/pyproject.toml /tmp/tars-mcp-character/pyproject.toml
COPY packages/tars-mcp-character/tars_mcp_character /tmp/tars-mcp-character/tars_mcp_character
COPY packages/tars-mcp-character/README.md /tmp/tars-mcp-character/README.md

RUN pip install --no-cache-dir /tmp/tars-mcp-character && \
    rm -rf /tmp/tars-mcp-character

# FastMCP CLI handles stdio/http/sse via command line
# Default to stdio, but compose.yml will override with sse --port 8000
CMD ["python", "-m", "tars_mcp_character", "stdio"]
