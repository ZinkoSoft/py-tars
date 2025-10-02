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

# Copy source code LAST (this layer invalidates most frequently)
COPY apps/llm-worker/llm_worker /app/llm_worker

ENV LOG_LEVEL=INFO

CMD ["python", "-m", "llm_worker"]
