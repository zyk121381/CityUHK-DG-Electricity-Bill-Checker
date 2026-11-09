# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_DIR=/app \
    TZ=Asia/Shanghai \
    RUN_AT=08:00 \
    RUN_ON_START=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime \
    && echo "$TZ" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY run.py config.example.yaml ./
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && mkdir -p /app/data /app/logs

VOLUME ["/app/data", "/app/logs"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["daemon"]
