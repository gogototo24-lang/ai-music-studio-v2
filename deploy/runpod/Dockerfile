FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/runpod-volume/huggingface \
    YUE2_MODEL=m-a-p/YuE2-3B \
    YUE2_DEVICE=cuda \
    YUE2_MEMORY_GIB=24

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    ffmpeg \
    libsndfile1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-runpod-yue2.txt /app/requirements-runpod-yue2.txt
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install --no-cache-dir -r /app/requirements-runpod-yue2.txt

COPY providers/runpod_yue2_handler.py /app/handler.py

CMD ["python3", "-u", "/app/handler.py"]
