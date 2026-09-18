# -*- coding: utf-8 -*-
"""
AI Music Studio v2
FastAPI backend for original lyrics, character voiceover, local BGM,
vocal separation, ducking mix, and 9:16 / 16:9 MV rendering.
"""
from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lyric_generator import LyricGenerator
from voice_engine import VoiceEngine
from music_engine import MusicEngine
from audio_extractor import AudioExtractor
from mixer import AudioMixer
from video_engine import VideoEngine

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="AI Music Studio v2", version="2.0.0")

default_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://gogototo24-lang.github.io",
]
extra = [x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(default_origins + extra)),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

lyric_gen = LyricGenerator()
voice_eng = VoiceEngine(output_dir=str(OUTPUT_DIR))
music_eng = MusicEngine(output_dir=str(OUTPUT_DIR))
audio_ext = AudioExtractor(output_dir=str(OUTPUT_DIR))
audio_mix = AudioMixer(output_dir=str(OUTPUT_DIR))
video_eng = VideoEngine(output_dir=str(OUTPUT_DIR))

SAFE_MEDIA = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "120"))


def safe_stem(name: str) -> str:
    stem = Path(name or "asset").stem
    stem = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", stem).strip("_")
    return (stem or "asset")[:50]


def unique_name(original: str, forced_ext: str | None = None) -> str:
    suffix = forced_ext or Path(original or "").suffix.lower()
    return f"{safe_stem(original)}_{uuid.uuid4().hex[:10]}{suffix}"


async def save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SAFE_MEDIA:
        raise HTTPException(status_code=400, detail=f"不支援的檔案格式：{suffix or '無副檔名'}")
    target = OUTPUT_DIR / unique_name(file.filename or f"upload{suffix}")
    total = 0
    with target.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_MB * 1024 * 1024:
                out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"單檔不可超過 {MAX_UPLOAD_MB} MB")
            out.write(chunk)
    return target


@app.get("/", response_class=HTMLResponse)
async def home():
    index_path = TEMPLATE_DIR / "index.html"
    return index_path.read_text(encoding="utf-8")


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "ai-music-studio-v2",
        "version": "2.0.0",
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "demucs": audio_ext.demucs_available(),
        "musicgen": music_eng.musicgen_available(),
    }


class LyricRequest(BaseModel):
    character_name: str = Field(default="月扇影喵", max_length=80)
    mode: str = "battle"
    language: str = "zh-TW"
    hook_strength: str = "strong"


@app.post("/api/lyrics/generate")
async def api_generate_lyrics(req: LyricRequest):
    return lyric_gen.generate(
        character_name=req.character_name,
        mode=req.mode,
        language=req.language,
        hook_strength=req.hook_strength,
    )


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    preset: str = "heroine"
    enable_reverb: bool = True


@app.post("/api/voice/generate")
async def api_generate_voice(req: VoiceRequest):
    filename = unique_name("voice.mp3", ".mp3")
    result = await voice_eng.generate_voice(
        text=req.text,
        preset_key=req.preset,
        enable_reverb=req.enable_reverb,
        filename=filename,
    )
    return {
        "status": "success",
        "audio_url": f"/outputs/{Path(result).name}",
        "filename": Path(result).name,
    }


class MusicRequest(BaseModel):
    style: str = "wuxia_epic"
    prompt: str = ""
    duration: int = Field(default=15, ge=5, le=180)


@app.post("/api/music/generate")
async def api_generate_music(req: MusicRequest):
    filename = unique_name("bgm.wav", ".wav")
    style_info = music_eng.get_style_info(req.style)
    prompt_to_use = req.prompt.strip() or style_info["tags"]
    result = music_eng.generate_local_bgm(
        prompt=prompt_to_use,
        duration=req.duration,
        output_filename=filename,
    )
    return {
        "status": "success",
        "audio_url": f"/outputs/{Path(result['path']).name}",
        "engine": result["engine"],
        "style_info": style_info,
        "note": result.get("note", ""),
    }


@app.post("/api/extract")
async def api_extract_audio(file: UploadFile = File(...)):
    source = await save_upload(file)
    try:
        result = audio_ext.separate_vocals(str(source))
        return {
            "status": "success",
            "engine": result["engine"],
            "vocal_url": f"/outputs/{Path(result['vocal_path']).name}",
            "bgm_url": f"/outputs/{Path(result['accompaniment_path']).name}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mix")
async def api_mix_audio(
    voice_file: UploadFile = File(...),
    bgm_file: UploadFile = File(...),
    voice_delay_ms: int = Form(900),
    bgm_volume: float = Form(0.38),
    ducking: bool = Form(True),
):
    voice_path = await save_upload(voice_file)
    bgm_path = await save_upload(bgm_file)
    out_filename = unique_name("mix.mp3", ".mp3")
    try:
        result = audio_mix.mix(
            voice_path=str(voice_path),
            bgm_path=str(bgm_path),
            output_filename=out_filename,
            bgm_volume=bgm_volume,
            voice_delay_ms=voice_delay_ms,
            ducking=ducking,
        )
        return {
            "status": "success",
            "audio_url": f"/outputs/{Path(result['path']).name}",
            "engine": result["engine"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mv/render")
async def api_render_mv(
    title: str = Form("AI Music Studio MV"),
    lyrics: str = Form(""),
    aspect: str = Form("9:16"),
    duration: int = Form(30),
    audio_file: UploadFile = File(...),
    media_files: List[UploadFile] = File(...),
):
    if not media_files:
        raise HTTPException(status_code=400, detail="至少需要一張圖片或一段影片")
    audio_path = await save_upload(audio_file)
    media_paths = [await save_upload(f) for f in media_files]
    out_filename = unique_name("music_video.mp4", ".mp4")
    try:
        result = video_eng.render_mv(
            media_paths=[str(p) for p in media_paths],
            audio_path=str(audio_path),
            title=title,
            lyrics=lyrics,
            duration=max(5, min(int(duration), 180)),
            aspect=aspect,
            output_filename=out_filename,
        )
        return {
            "status": "success",
            "video_url": f"/outputs/{Path(result['path']).name}",
            "subtitle_url": f"/outputs/{Path(result['subtitle_path']).name}" if result.get("subtitle_path") else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/outputs/cleanup")
async def cleanup_outputs():
    count = 0
    for p in OUTPUT_DIR.iterdir():
        if p.is_file():
            p.unlink(missing_ok=True)
            count += 1
        elif p.is_dir() and p.name.startswith("_"):
            shutil.rmtree(p, ignore_errors=True)
    return {"status": "success", "deleted": count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
