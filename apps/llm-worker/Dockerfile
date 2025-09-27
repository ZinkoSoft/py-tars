FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY apps/llm-worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/llm-worker/ /app/
COPY src /app/src
ENV PYTHONPATH="/app/src:${PYTHONPATH}"

ENV LOG_LEVEL=INFO

CMD ["python", "-m", "llm_worker"]
