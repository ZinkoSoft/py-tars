FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY memory_worker ./memory_worker

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/data/model_cache \
    SENTENCE_TRANSFORMERS_HOME=/data/model_cache \
    TRANSFORMERS_CACHE=/data/model_cache \
    TORCH_HOME=/data/model_cache

CMD ["python", "-m", "memory_worker"]
