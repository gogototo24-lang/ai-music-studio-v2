# -*- coding: utf-8 -*-
"""
Standard adapter for a separately deployed CosyVoice service.

Expected layout:
- clone QwenAudio/CosyVoice
- set COSYVOICE_REPO to that checkout
- set COSYVOICE_MODEL_DIR
- set VOICE_REFERENCE_DIR with <reference_id>.wav and optional <reference_id>.txt

This adapter exposes the AI Music Studio contract:
POST /synthesize -> WAV bytes
"""
from __future__ import annotations

import io
import os
import sys
import wave
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

COSYVOICE_REPO = Path(os.getenv("COSYVOICE_REPO", "/opt/CosyVoice"))
MODEL_DIR = os.getenv("COSYVOICE_MODEL_DIR", "FunAudioLLM/Fun-CosyVoice3-0.5B-2512")
REFERENCE_DIR = Path(os.getenv("VOICE_REFERENCE_DIR", "/data/voices"))

sys.path.insert(0, str(COSYVOICE_REPO))
sys.path.insert(0, str(COSYVOICE_REPO / "third_party" / "Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402
from cosyvoice.utils.file_utils import load_wav  # noqa: E402

app = FastAPI(title="CosyVoice Adapter")
model = AutoModel(model_dir=MODEL_DIR)


class Request(BaseModel):
    text: str
    preset: str = "heroine"
    language: str = "zh"
    emotion: str = "neutral"
    reference_id: str = ""


def wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    arr = np.asarray(samples).reshape(-1)
    arr = np.clip(arr, -1.0, 1.0)
    pcm = (arr * 32767.0).astype(np.int16)
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return bio.getvalue()


@app.get("/health")
def health():
    return {"ok": True, "provider": "cosyvoice", "model": MODEL_DIR}


@app.post("/synthesize")
def synthesize(req: Request):
    reference_id = req.reference_id or os.getenv("COSYVOICE_DEFAULT_REFERENCE", "")
    if not reference_id:
        raise HTTPException(400, "CosyVoice 需要 reference_id 或 COSYVOICE_DEFAULT_REFERENCE")

    wav_path = REFERENCE_DIR / f"{reference_id}.wav"
    txt_path = REFERENCE_DIR / f"{reference_id}.txt"
    if not wav_path.exists():
        raise HTTPException(404, f"找不到參考聲線：{reference_id}.wav")

    prompt_text = txt_path.read_text(encoding="utf-8").strip() if txt_path.exists() else ""
    prompt_speech = load_wav(str(wav_path), 16000)

    instruct = ""
    if req.language in {"zh-minnan", "minnan", "taiwanese"}:
        instruct += "請使用閩南語口音。"
    if req.emotion and req.emotion != "neutral":
        instruct += f"情緒：{req.emotion}。"

    chunks = []
    try:
        if instruct and hasattr(model, "inference_instruct2"):
            iterator = model.inference_instruct2(req.text, instruct, prompt_speech, stream=False)
        else:
            iterator = model.inference_zero_shot(req.text, prompt_text, prompt_speech, stream=False)
        for item in iterator:
            chunks.append(item["tts_speech"].detach().cpu().numpy())
    except Exception as exc:
        raise HTTPException(500, str(exc))

    if not chunks:
        raise HTTPException(500, "CosyVoice 沒有產生音訊")
    audio = np.concatenate([x.reshape(-1) for x in chunks])
    return Response(wav_bytes(audio, model.sample_rate), media_type="audio/wav")
