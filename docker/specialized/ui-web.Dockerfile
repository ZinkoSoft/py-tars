FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ARG SERVICE_PATH=.

WORKDIR /app

# Copy package configuration and source code
COPY ${SERVICE_PATH}/pyproject.toml ./
COPY ${SERVICE_PATH}/src ./src
COPY ${SERVICE_PATH}/static ./static

# Install the package
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

ENV MQTT_URL="mqtt://tars:pass@127.0.0.1:1883"

# Use the installed CLI command
CMD ["tars-ui-web"]
