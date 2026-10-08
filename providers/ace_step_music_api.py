# -*- coding: utf-8 -*-
"""
Standard CatPaw wrapper for an ACE-Step deployment.

This service is intentionally separate from the main API because ACE-Step is a
GPU workload. The wrapper accepts the same /synthesize contract as YuE2.

NOTE: ACE-Step versions expose different Python generation APIs. Set
ACESTEP_UPSTREAM_URL to a compatible ACE-Step service that accepts /generate.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

UPSTREAM = os.getenv("ACESTEP_UPSTREAM_URL", "").strip().rstrip("/")
app = FastAPI(title="CatPaw ACE-Step Music Adapter")


class SongRequest(BaseModel):
    title: str = ""
    style: str = ""
    prompt: str = ""
    lyrics: str = Field(default="", max_length=12000)
    duration: int = Field(default=60, ge=5, le=240)
    seed: int | None = None


@app.get("/health")
def health():
    return {"ok": bool(UPSTREAM), "provider": "ace-step", "configured": bool(UPSTREAM)}


@app.post("/synthesize")
async def synthesize(req: SongRequest):
    if not UPSTREAM:
        raise HTTPException(503, "尚未設定 ACESTEP_UPSTREAM_URL")

    combined = req.style
    if req.prompt:
        combined += f", {req.prompt}"
    if req.lyrics:
        combined += "\nLyrics:\n" + req.lyrics

    async with httpx.AsyncClient(timeout=600.0) as client:
        r = await client.post(
            f"{UPSTREAM}/generate",
            json={
                "prompt": combined,
                "duration": req.duration,
                "infer_steps": 27,
                "guidance_scale": 15.0,
                "omega_scale": 10.0,
                "seed": req.seed,
            },
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:500])

    data = r.json()
    audio_path = data.get("audio_path")
    if not audio_path:
        raise HTTPException(500, "ACE-Step upstream 沒有回傳 audio_path")

    # This wrapper expects shared storage or a mounted output directory.
    source = Path(audio_path)
    if not source.exists():
        raise HTTPException(500, "找不到 ACE-Step 產生的音檔；請配置 shared storage")
    return FileResponse(str(source), media_type="audio/wav", filename="catpaw-ace-step.wav")
