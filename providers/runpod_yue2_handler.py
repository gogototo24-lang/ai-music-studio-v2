# -*- coding: utf-8 -*-
"""
CatPaw YuE2 worker for RunPod Serverless queue endpoints.

Input:
{
  "input": {
    "title": "...",
    "style": "...",
    "prompt": "...",
    "lyrics": "...",
    "duration": 60,
    "seed": 42,
    "output_format": "flac"
  }
}

Output:
{
  "audio_base64": "...",
  "format": "flac",
  "model": "m-a-p/YuE2-3B"
}
"""
from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

import runpod
from yue2 import YuE2Pipeline

MODEL = os.getenv("YUE2_MODEL", "m-a-p/YuE2-3B")
VAE = os.getenv("YUE2_VAE", "") or None
DEVICE = os.getenv("YUE2_DEVICE", "cuda")
MEMORY_GIB = float(os.getenv("YUE2_MEMORY_GIB", "24"))

pipe = YuE2Pipeline.from_pretrained(
    MODEL,
    vae=VAE,
    device=DEVICE,
    memory_budget_gib=MEMORY_GIB,
)


def handler(event):
    data = (event or {}).get("input") or {}
    lyrics = str(data.get("lyrics") or "").strip()
    if not lyrics:
        return {"error": "lyrics is required"}

    style = str(data.get("style") or "cinematic wuxia female vocal").strip()
    prompt = str(data.get("prompt") or "").strip()
    if prompt:
        style = f"{style}, {prompt}"

    seed = data.get("seed")
    fmt = str(data.get("output_format") or "flac").lower()
    if fmt not in {"flac", "wav"}:
        fmt = "flac"

    song = pipe(
        style=style,
        lyrics=lyrics,
        cot="full",
        seed=seed,
    )

    out = Path(tempfile.gettempdir()) / f"catpaw_runpod_yue2.{fmt}"
    song.save(out)
    raw = out.read_bytes()
    if len(raw) < 1024:
        raise RuntimeError("YuE2 produced an invalid audio file")

    return {
        "audio_base64": base64.b64encode(raw).decode("ascii"),
        "format": fmt,
        "model": MODEL,
        "title": str(data.get("title") or ""),
        "bytes": len(raw),
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
