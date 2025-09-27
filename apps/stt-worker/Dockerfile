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
COPY apps/stt-worker/requirements.txt ./requirements.txt
COPY packages/tars-core /tmp/tars-core
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Copy application modules
COPY apps/stt-worker/main.py ./main.py
COPY apps/stt-worker/config.py ./config.py
COPY apps/stt-worker/audio_capture.py ./audio_capture.py
COPY apps/stt-worker/audio_fanout.py ./audio_fanout.py
COPY apps/stt-worker/vad.py ./vad.py
COPY apps/stt-worker/transcriber.py ./transcriber.py
COPY apps/stt-worker/mqtt_utils.py ./mqtt_utils.py
COPY apps/stt-worker/suppression.py ./suppression.py
COPY apps/stt-worker/audio_preproc.py ./audio_preproc.py

# Create directories for models
RUN mkdir -p /app/models /host-models

# Set Hugging Face cache environment variables
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/models
ENV HUGGINGFACE_HUB_CACHE=/app/models
ENV TRANSFORMERS_CACHE=/app/models

# Use entrypoint to copy models from host mount if available
ENTRYPOINT ["/bin/sh", "-c", "if [ -d /host-models ] && [ -n \"$(ls -A /host-models 2>/dev/null)\" ]; then echo 'Copying models from host...'; cp -r /host-models/* /app/models/ 2>/dev/null || true; fi; exec python /app/main.py"]
