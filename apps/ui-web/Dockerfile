FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MQTT_URL="mqtt://tars:pass@127.0.0.1:1883" \
    HOST=0.0.0.0 \
    PORT=5010

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5010"]