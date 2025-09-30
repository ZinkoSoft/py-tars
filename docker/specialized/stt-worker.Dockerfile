FROM python:3.11-slim

# Install system dependencies for audio and Faster-Whisper
RUN apt-get update && apt-get install -y --no-install-recommends \
    alsa-utils \
    pulseaudio-utils \
    portaudio19-dev \
    python3-dev \
    gcc \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY apps/stt-worker/pyproject.toml ./pyproject.toml
COPY apps/stt-worker/README.md ./README.md
COPY apps/stt-worker/requirements.txt ./requirements.txt
COPY apps/stt-worker/stt_worker ./stt_worker
COPY packages/tars-core /tmp/tars-core
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Copy application source including compatibility shims and entrypoint modules
COPY apps/stt-worker/ /app/

# Create directories for models
RUN mkdir -p /app/models /host-models

# Set Hugging Face cache environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/models
ENV HUGGINGFACE_HUB_CACHE=/app/models
ENV TRANSFORMERS_CACHE=/app/models

# Use entrypoint to copy models from host mount if available
ENTRYPOINT ["/bin/sh", "-c", "if [ -d /host-models ] && [ -n \"$(ls -A /host-models 2>/dev/null)\" ]; then echo 'Copying models from host...'; cp -r /host-models/* /app/models/ 2>/dev/null || true; fi; exec python /app/main.py"]
