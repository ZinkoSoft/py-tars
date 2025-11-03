# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE} as runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/ui-eink-display

# Install system dependencies for e-ink display
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3-dev \
        python3-pil \
        python3-numpy \
        fonts-dejavu-core \
        libgpiod-dev \
        git \
        wget \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install tars-core first (required for contracts)
COPY packages/tars-core/pyproject.toml packages/tars-core/README.md /tmp/tars-core/
COPY packages/tars-core/src /tmp/tars-core/src
RUN pip install --upgrade pip && \
    pip install /tmp/tars-core && \
    rm -rf /tmp/tars-core

# Install dependencies ONLY (don't install the package itself)
COPY apps/ui-eink-display/pyproject.toml ./pyproject.toml

# Install base dependencies
RUN python -c "import tomllib; data = tomllib.load(open('pyproject.toml','rb')); deps = data['project']['dependencies']; print('\\n'.join(deps))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Clone and setup waveshare e-Paper library
RUN git clone --depth=1 https://github.com/waveshare/e-Paper.git /opt/e-Paper \
    && cd /opt/e-Paper/RaspberryPi_JetsonNano/python \
    && python setup.py install || echo "waveshare-epd setup.py install failed, will use PYTHONPATH"

# Source code will be provided via volume mount at /workspace/apps/ui-eink-display
# This enables live code updates without container rebuild

ENV PYTHONPATH=/workspace/apps/ui-eink-display/src:/opt/e-Paper/RaspberryPi_JetsonNano/python/lib

CMD ["python", "-m", "ui_eink_display"]
