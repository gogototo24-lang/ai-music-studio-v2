# -*- coding: utf-8 -*-
"""
Standalone self-hosted YuE2 song service.

Run this on a GPU machine/container, separate from the lightweight main API.
The main AI Music Studio calls POST /synthesize.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from yue2 import YuE2Pipeline

MODEL = os.getenv("YUE2_MODEL", "m-a-p/YuE2-3B")
DEVICE = os.getenv("YUE2_DEVICE", "cuda")
MEMORY_GIB = float(os.getenv("YUE2_MEMORY_GIB", "24"))
VAE = os.getenv("YUE2_VAE", "") or None

app = FastAPI(title="CatPaw YuE2 Music API")
pipe = YuE2Pipeline.from_pretrained(
    MODEL,
    vae=VAE,
    device=DEVICE,
    memory_budget_gib=MEMORY_GIB,
)


class SongRequest(BaseModel):
    title: str = ""
    style: str = "cinematic wuxia female vocal"
    prompt: str = ""
    lyrics: str = Field(default="", max_length=12000)
    duration: int = Field(default=60, ge=5, le=600)
    seed: int | None = None


@app.get("/health")
def health():
    return {
        "ok": True,
        "provider": "yue2",
        "model": MODEL,
        "device": DEVICE,
    }


@app.post("/synthesize")
def synthesize(req: SongRequest):
    if not req.lyrics.strip():
        raise HTTPException(400, "YuE2 完整歌曲模式需要歌詞")

    style = req.style.strip()
    if req.prompt.strip():
        style = f"{style}, {req.prompt.strip()}"

    try:
        song = pipe(
            style=style,
            lyrics=req.lyrics,
            cot="full",
            seed=req.seed,
        )
        out = Path(tempfile.gettempdir()) / f"catpaw_yue2_{os.getpid()}_{req.seed or 'auto'}.wav"
        song.save(out)
    except Exception as exc:
        raise HTTPException(500, str(exc))

    if not out.exists() or out.stat().st_size < 1024:
        raise HTTPException(500, "YuE2 沒有產生有效音訊")

    return FileResponse(str(out), media_type="audio/wav", filename="catpaw-song.wav")
