FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxrandr2 \
    libxcursor1 \
    libxi6 \
    libsdl2-2.0-0 \
    libsdl2-ttf-2.0-0 \
    fonts-dejavu-core \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY apps/ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY apps/ui/ /app/

ENV UI_CONFIG="/config/ui.toml"

CMD ["python", "-u", "main.py"]
