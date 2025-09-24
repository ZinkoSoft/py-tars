# syntax=docker/dockerfile:1.6
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/wake-training

# Base utilities that both the API and training worker will need. Adjust as
# implementation solidifies.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Optional requirements file; installing is skipped when the file is empty.
COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && \
    if [ -s requirements.txt ]; then \
        python -m pip install -r requirements.txt; \
    fi

# Copy application code
COPY wake_training ./wake_training

ENV PYTHONPATH=/opt/wake-training

CMD [
    "uvicorn",
    "wake_training.main:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8080"
]
