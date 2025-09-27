# Router service Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies (if any future native deps needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY apps/router/pyproject.toml ./pyproject.toml
# Use pip to install deps specified in pyproject (simple approach)
RUN pip install --upgrade pip && \
    pip install .[all] 2>/dev/null || true && \
    pip install asyncio-mqtt orjson uvloop

COPY src /app/src
ENV PYTHONPATH="/app/src:${PYTHONPATH}"

COPY apps/router/main.py ./main.py
CMD ["python", "main.py"]
