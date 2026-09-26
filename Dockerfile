# Multi-stage Dockerfile for AI Music Studio v2
# Stage 1: Base image with system dependencies
FROM python:3.11-slim as base

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Stage 2: Lite mode (FFmpeg + Edge TTS only)
FROM base as lite

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
ENV MODE=lite
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["python", "app.py"]

# Stage 3: Full AI mode (with MusicGen/Demucs)
FROM base as ai

COPY requirements.txt requirements-ai.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-ai.txt

COPY . .

ENV PORT=8000
ENV MODE=ai
ENV MUSICGEN_DEVICE=cpu
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["python", "app.py"]

# Default: Lite mode
FROM lite
