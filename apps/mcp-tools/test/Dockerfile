FROM python:3.12-slim

WORKDIR /app

# Install FastMCP
RUN pip install --no-cache-dir "mcp[cli]"

# Copy server file
COPY test_server.py /app/server.py

# Expose HTTP port
EXPOSE 8080

# Run FastMCP server on HTTP
CMD ["python", "server.py"]
