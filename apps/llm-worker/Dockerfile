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

# Install the worker as a wheel to match the centralized build flow
COPY apps/llm-worker/pyproject.toml /tmp/llm-worker/pyproject.toml
COPY apps/llm-worker/README.md /tmp/llm-worker/README.md
COPY apps/llm-worker/llm_worker /tmp/llm-worker/llm_worker
RUN pip install --no-cache-dir /tmp/llm-worker && \
    rm -rf /tmp/llm-worker

ENV LOG_LEVEL=INFO

CMD ["python", "-m", "llm_worker"]
