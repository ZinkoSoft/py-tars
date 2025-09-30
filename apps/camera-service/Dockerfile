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

# Install Python dependencies
WORKDIR /app
COPY apps/camera-service/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application source
COPY apps/camera-service/ /app/

# Set environment
ENV PYTHONUNBUFFERED=1

# Run the service
CMD ["python", "/app/main.py"]