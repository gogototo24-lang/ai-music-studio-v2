# -*- coding: utf-8 -*-
"""
Standard adapter for AMAPVOICE/PilotTTS.

Deploy on a GPU-capable service. The lite Render app should call this adapter
over HTTP instead of installing the model locally.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

PILOT_REPO = Path(os.getenv("PILOTTTS_REPO", "/opt/PilotTTS"))
REFERENCE_DIR = Path(os.getenv("VOICE_REFERENCE_DIR", "/data/voices"))
CONFIG = os.getenv("PILOTTTS_CONFIG", "configs/infer_pilot_tts_instruct.yaml")
CHECKPOINT = os.getenv("PILOTTTS_CHECKPOINT", "pretrained_models/pilot_tts_instruct.pt")

sys.path.insert(0, str(PILOT_REPO))
from demo import load_engine, synthesize  # noqa: E402

app = FastAPI(title="PilotTTS Adapter")
engine = load_engine(config_path=str(PILOT_REPO / CONFIG), checkpoint=str(PILOT_REPO / CHECKPOINT))


class Request(BaseModel):
    text: str
    preset: str = "heroine"
    language: str = "zh-minnan"
    emotion: str = "neutral"
    reference_id: str = ""


@app.get("/health")
def health():
    return {"ok": True, "provider": "pilottts", "language": "zh-minnan"}


@app.post("/synthesize")
def synthesize_api(req: Request):
    reference_id = req.reference_id or os.getenv("PILOTTTS_DEFAULT_REFERENCE", "")
    if not reference_id:
        raise HTTPException(400, "PilotTTS 需要 reference_id 或 PILOTTTS_DEFAULT_REFERENCE")
    wav_path = REFERENCE_DIR / f"{reference_id}.wav"
    if not wav_path.exists():
        raise HTTPException(404, f"找不到參考聲線：{reference_id}.wav")

    language = req.language or "zh-minnan"
    if language in {"minnan", "taiwanese", "nan-tw"}:
        language = "zh-minnan"

    output = Path(tempfile.gettempdir()) / f"pilot_{os.getpid()}_{reference_id}.wav"
    try:
        synthesize(
            engine,
            text=req.text,
            prompt_wav=str(wav_path),
            output_path=str(output),
            language=language,
            emotion=req.emotion or "neutral",
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))
    if not output.exists():
        raise HTTPException(500, "PilotTTS 沒有產生音訊")
    return FileResponse(str(output), media_type="audio/wav", filename="voice.wav")
