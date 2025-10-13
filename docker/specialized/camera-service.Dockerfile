FROM python:3.11-slim

# Install system dependencies for camera access
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    gcc \
    ca-certificates \
    libcamera-dev \
    libjpeg-dev \
    libpng-dev \
    libcap-dev \
    python3-libcamera \
    libgl1 \
    libegl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set up workspace
WORKDIR /workspace

# Copy application with src/ layout
COPY apps/camera-service/ /workspace/apps/camera-service/

# Install package in editable mode
RUN pip install --upgrade pip && \
    pip install -e /workspace/apps/camera-service

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace/apps/camera-service/src

# Run the service using module entrypoint
CMD ["python", "-m", "camera_service"]
