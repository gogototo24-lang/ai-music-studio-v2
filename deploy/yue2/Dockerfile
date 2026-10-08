FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8010

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-yue2.txt /app/requirements-yue2.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /app/requirements-yue2.txt

COPY providers /app/providers

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD curl -f http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh","-c","uvicorn providers.yue2_music_api:app --host 0.0.0.0 --port ${PORT:-8010}"]
