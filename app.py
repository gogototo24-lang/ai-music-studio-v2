# -*- coding: utf-8 -*-
"""
AI Music Studio v2
FastAPI backend for original lyrics, character voiceover, local BGM,
vocal separation, ducking mix, and 9:16 / 16:9 MV rendering.
"""
from __future__ import annotations

import os
import json
import re
import shutil
import threading
import uuid
import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse
from typing import List

import httpx

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from lyric_generator import LyricGenerator
from voice_engine import VoiceEngine, CHARACTER_PRESETS, public_voice_presets
from voice_router import VoiceProviderRouter
from music_engine import MusicEngine
from music_router import MusicProviderRouter
from audio_extractor import AudioExtractor
from mixer import AudioMixer
from video_engine import VideoEngine, MAX_DURATION, MAX_MEDIA
from editor_engine import EditorEngine
from music_analyzer import MusicAnalyzer

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
TEMPLATE_DIR = BASE_DIR / "templates"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="AI Music Studio v2", version="2.8.0")

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
voice_router = VoiceProviderRouter(voice_eng, output_dir=str(OUTPUT_DIR))
music_eng = MusicEngine(output_dir=str(OUTPUT_DIR))
music_router = MusicProviderRouter(music_eng, output_dir=str(OUTPUT_DIR))
audio_ext = AudioExtractor(output_dir=str(OUTPUT_DIR))
audio_mix = AudioMixer(output_dir=str(OUTPUT_DIR))
video_eng = VideoEngine(output_dir=str(OUTPUT_DIR))
editor_eng = EditorEngine(output_dir=str(OUTPUT_DIR))
music_analyzer = MusicAnalyzer(output_dir=str(OUTPUT_DIR))

SAFE_MEDIA = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "120"))
JOBS: dict = {}
JOBS_LOCK = threading.Lock()


def safe_stem(name: str) -> str:
    stem = Path(name or "asset").stem
    stem = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", stem).strip("_")
    return (stem or "asset")[:50]


def unique_name(original: str, forced_ext: str | None = None) -> str:
    suffix = forced_ext or Path(original or "").suffix.lower()
    return f"{safe_stem(original)}_{uuid.uuid4().hex[:10]}{suffix}"


def _validate_remote_url(raw: str) -> str:
    try:
        parsed = urlparse(raw)
    except Exception:
        raise HTTPException(status_code=422, detail="遠端素材 URL 格式錯誤")
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=422, detail="遠端素材只允許 HTTPS")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise HTTPException(status_code=422, detail="不允許本機或私有網路 URL")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                raise HTTPException(status_code=422, detail="不允許解析到私有網路的 URL")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="遠端素材網域無法解析")
    return raw


async def download_remote_media(raw_url: str, kind: str) -> Path:
    url = _validate_remote_url(raw_url)
    allowed = {
        "video": {".mp4", ".mov", ".webm"},
        "audio": {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"},
    }[kind]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in allowed:
        suffix = ".mp4" if kind == "video" else ".mp3"
    target = OUTPUT_DIR / unique_name(f"remote{suffix}", suffix)
    total = 0
    timeout = httpx.Timeout(60.0, connect=20.0)
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        async with client.stream("GET", url, headers={"User-Agent": "CatPaw-Editor/0.4"}) as resp:
            if resp.status_code >= 400:
                raise HTTPException(status_code=422, detail=f"遠端素材下載失敗：HTTP {resp.status_code}")
            final_url = str(resp.url)
            _validate_remote_url(final_url)
            content_type = (resp.headers.get("content-type") or "").lower()
            if kind == "video" and not ("video/" in content_type or "octet-stream" in content_type):
                raise HTTPException(status_code=422, detail=f"遠端影片 content-type 不符：{content_type or 'unknown'}")
            if kind == "audio" and not ("audio/" in content_type or "octet-stream" in content_type):
                raise HTTPException(status_code=422, detail=f"遠端音訊 content-type 不符：{content_type or 'unknown'}")
            with target.open("wb") as out:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_UPLOAD_MB * 1024 * 1024:
                        target.unlink(missing_ok=True)
                        raise HTTPException(status_code=413, detail=f"遠端單檔不可超過 {MAX_UPLOAD_MB} MB")
                    out.write(chunk)
    return target


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


def _set_job(job_id: str, **fields):
    with JOBS_LOCK:
        JOBS.setdefault(job_id, {})
        JOBS[job_id].update(fields)


def _run_editor_job(job_id: str, kwargs: dict):
    _set_job(job_id, status="running", job_type="editor")
    try:
        result = editor_eng.render(**kwargs)
        _set_job(
            job_id,
            status="success",
            job_type="editor",
            video_url=f"/outputs/{Path(result['path']).name}",
            meta={k: v for k, v in result.items() if k != "path"},
        )
    except Exception as e:
        _set_job(job_id, status="error", job_type="editor", detail=str(e))


def _run_mv_job(job_id: str, kwargs: dict):
    _set_job(job_id, status="running")
    try:
        result = video_eng.render_mv(**kwargs)
        _set_job(
            job_id,
            status="success",
            video_url=f"/outputs/{Path(result['path']).name}",
            subtitle_url=f"/outputs/{Path(result['subtitle_path']).name}" if result.get("subtitle_path") else None,
            meta={
                "width": result.get("width"),
                "height": result.get("height"),
                "fps": result.get("fps"),
                "duration": result.get("duration"),
                "media_count": result.get("media_count"),
                "subtitles_burned": result.get("subtitles_burned"),
            },
        )
    except Exception as e:
        _set_job(job_id, status="error", detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def home():
    index_path = TEMPLATE_DIR / "index.html"
    return index_path.read_text(encoding="utf-8")


@app.get("/health")
async def health():
    runtime = music_eng.runtime_status()
    return {
        "ok": True,
        "service": "ai-music-studio-v2",
        "version": "2.8.0",
        "ffmpeg": runtime["ffmpeg_available"],
        "voice_providers": voice_router.provider_status(),
        "music_providers": music_router.status(),
        "musicgen": runtime["musicgen_available"],
        "cuda_available": runtime["cuda_available"],
        "device": runtime["device"],
        "model_name": runtime["model_name"],
        "fallback_enabled": runtime["fallback_enabled"],
        "demucs": audio_ext.demucs_available(),
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


@app.get("/api/voice/presets")
async def api_voice_presets():
    return {
        "presets": public_voice_presets(),
        "providers": voice_router.provider_status(),
        "language_note": "Edge 為台灣中文 fallback；台語／閩南語正式測試優先 PilotTTS zh-minnan 與 CosyVoice。",
    }


@app.get("/api/voice/providers")
async def api_voice_providers():
    return {
        "providers": voice_router.provider_status(),
        "recommended": {
            "zh-TW": "runninghub",
            "zh-minnan": "pilottts",
            "character_clone": "runninghub / gpt-sovits / cosyvoice",
        },
    }


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    preset: str = "heroine"
    provider: str = "auto"
    language: str = "zh-TW"
    emotion: str = "neutral"
    reference_id: str = ""
    enable_reverb: bool = True


@app.post("/api/voice/generate")
async def api_generate_voice(req: VoiceRequest):
    if req.preset not in CHARACTER_PRESETS:
        raise HTTPException(status_code=400, detail=f"未知聲線 preset：{req.preset}")
    try:
        result = await voice_router.generate(
            text=req.text,
            preset=req.preset,
            provider=req.provider,
            language=req.language,
            emotion=req.emotion,
            reference_id=req.reference_id,
            enable_reverb=req.enable_reverb,
            filename_stem=f"voice_{uuid.uuid4().hex[:10]}",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    preset = CHARACTER_PRESETS[req.preset]
    path = Path(result["path"])
    return {
        "status": "success",
        "audio_url": f"/outputs/{path.name}",
        "filename": path.name,
        "preset": req.preset,
        "preset_name": preset["name"],
        "provider": result["provider"],
        "provider_name": result["provider_name"],
        "language": result["language"],
        "emotion": result["emotion"],
        "fallback_used": result.get("fallback_used", False),
        "attempted_providers": result.get("attempted_providers", [result["provider"]]),
    }


class RemoteEditorRequest(BaseModel):
    clip_urls: List[str] = Field(min_length=1, max_length=30)
    music_url: str | None = None
    trim_specs: List[dict] = Field(default_factory=list)
    aspect: str = "9:16"
    quality: str = "720p"
    transition: str = "cut"
    target_seconds: float = Field(default=30, ge=1, le=900)
    original_audio_volume: float = Field(default=0.18, ge=0, le=1)
    title_text: str = Field(default="", max_length=120)
    ending_text: str = Field(default="", max_length=120)
    reuse_mode: str = "cycle"


class MusicRequest(BaseModel):
    provider: str = "auto"
    title: str = ""
    style: str = "wuxia_epic"
    prompt: str = ""
    lyrics: str = ""
    duration: int = Field(default=60, ge=5, le=600)
    seed: int | None = None
    use_fallback: bool = True


@app.get("/api/music/providers")
async def api_music_providers():
    return {
        "providers": music_router.status(),
        "recommended": {
            "bgm": "musicgen",
            "full_song": "runpod-yue2",
            "fast_candidate": "ace-step",
        },
    }


@app.post("/api/music/generate")
async def api_generate_music(req: MusicRequest):
    try:
        result = await music_router.generate(
            provider=req.provider,
            style=req.style,
            prompt=req.prompt,
            lyrics=req.lyrics,
            duration=req.duration,
            seed=req.seed,
            title=req.title,
            use_fallback=req.use_fallback,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    path = Path(result["path"])
    return {
        "status": "success",
        "audio_url": f"/outputs/{path.name}",
        "engine": result["engine"],
        "provider_name": result.get("provider_name"),
        "full_song": result.get("full_song", False),
        "lyrics_supported": result.get("lyrics_supported", False),
        "note": result.get("note", ""),
    }


@app.get("/api/music/status")
async def api_music_status():
    return {
        **music_eng.runtime_status(),
        "providers": music_router.status(),
    }


@app.get("/api/editor/status")
async def api_editor_status():
    return {
        "ok": True,
        "name": "CatPaw AI 剪輯師",
        "version": "0.4",
        "engine": "ffmpeg",
        "audio_extract": True,
        "music_analysis": True,
        "bpm_estimate": True,
        "chorus_candidates": True,
        "remote_url_ingest": True,
        "max_clips": 30,
        "aspects": ["9:16", "16:9"],
        "qualities": ["720p", "1080p"],
        "transitions": ["cut", "fade"],
        "target_presets_seconds": [30, 60, 275],
        "music_track": True,
        "full_mv_reuse": True,
        "title_cards": True,
        "gpu_required": False,
    }



@app.post("/api/editor/extract-audio")
async def api_editor_extract_audio(
    file: UploadFile = File(...),
    bitrate: str = Form("320k"),
):
    source = await save_upload(file)
    if source.suffix.lower() not in {".mp4", ".mov", ".webm", ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}:
        raise HTTPException(status_code=422, detail="不支援的音訊／影片格式")
    if bitrate not in {"192k", "256k", "320k"}:
        bitrate = "320k"
    out_filename = unique_name("catpaw_audio.mp3", ".mp3")
    try:
        result = music_analyzer.extract_audio(str(source), out_filename, bitrate=bitrate)
        return {
            "status": "success",
            "audio_url": f"/outputs/{Path(result['path']).name}",
            "duration": result["duration"],
            "bitrate": result["bitrate"],
            "format": result["format"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/editor/analyze-music")
async def api_editor_analyze_music(file: UploadFile = File(...)):
    source = await save_upload(file)
    if source.suffix.lower() not in {".mp4", ".mov", ".webm", ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}:
        raise HTTPException(status_code=422, detail="不支援的音訊／影片格式")
    try:
        return {"status": "success", **music_analyzer.analyze(str(source))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/editor/render-from-urls")
async def api_editor_render_from_urls(req: RemoteEditorRequest):
    if req.aspect not in {"9:16", "16:9"}:
        raise HTTPException(status_code=422, detail="aspect 只支援 9:16 / 16:9")
    if req.quality not in {"720p", "1080p"}:
        raise HTTPException(status_code=422, detail="quality 只支援 720p / 1080p")
    if req.transition not in {"cut", "fade"}:
        raise HTTPException(status_code=422, detail="transition 只支援 cut / fade")
    if req.reuse_mode != "cycle":
        raise HTTPException(status_code=422, detail="reuse_mode 目前只支援 cycle")

    clip_paths = []
    try:
        for url in req.clip_urls:
            clip_paths.append(await download_remote_media(url, "video"))
        music_path = await download_remote_media(req.music_url, "audio") if req.music_url else None
    except Exception:
        for p in clip_paths:
            p.unlink(missing_ok=True)
        raise

    trims = req.trim_specs or [{} for _ in clip_paths]
    if len(trims) != len(clip_paths):
        raise HTTPException(status_code=422, detail="trim_specs 數量必須與 clip_urls 相同")

    music_analysis = None
    if music_path:
        try:
            music_analysis = music_analyzer.analyze(str(music_path))
        except Exception:
            music_analysis = None

    out_filename = unique_name("catpaw_remote_edit.mp4", ".mp4")
    job_id = uuid.uuid4().hex[:12]
    kwargs = {
        "clip_paths": [str(p) for p in clip_paths],
        "trim_specs": trims,
        "aspect": req.aspect,
        "quality": req.quality,
        "transition": req.transition,
        "output_filename": out_filename,
        "fps": 24,
        "target_seconds": req.target_seconds,
        "music_path": str(music_path) if music_path else None,
        "original_audio_volume": req.original_audio_volume,
        "title_text": req.title_text,
        "ending_text": req.ending_text,
        "reuse_mode": req.reuse_mode,
    }
    _set_job(
        job_id,
        status="queued",
        job_type="editor",
        remote_ingest=True,
        music_analysis=music_analysis,
        source_clip_count=len(clip_paths),
    )
    threading.Thread(target=_run_editor_job, args=(job_id, kwargs), daemon=True).start()
    return {
        "status": "queued",
        "job_id": job_id,
        "job_type": "editor",
        "remote_ingest": True,
        "music_analysis": music_analysis,
    }


@app.post("/api/editor/render")
async def api_editor_render(
    aspect: str = Form("9:16"),
    quality: str = Form("720p"),
    transition: str = Form("cut"),
    trim_json: str = Form("[]"),
    target_seconds: float = Form(0),
    original_audio_volume: float = Form(0.18),
    title_text: str = Form(""),
    ending_text: str = Form(""),
    reuse_mode: str = Form("cycle"),
    music_file: UploadFile | None = File(None),
    clips: List[UploadFile] = File(...),
):
    if not clips:
        raise HTTPException(status_code=400, detail="至少需要一支影片")
    if len(clips) > 30:
        raise HTTPException(status_code=400, detail="v0.2 一次最多 30 支影片")
    try:
        trims = json.loads(trim_json or "[]")
    except Exception:
        raise HTTPException(status_code=422, detail="trim_json 必須是合法 JSON")
    if trims and not isinstance(trims, list):
        raise HTTPException(status_code=422, detail="trim_json 必須是陣列")
    clip_paths = [await save_upload(f) for f in clips]
    if any(p.suffix.lower() not in {".mp4", ".mov", ".webm"} for p in clip_paths):
        raise HTTPException(status_code=422, detail="CatPaw Editor v0.2 目前只接受影片素材")
    out_filename = unique_name("catpaw_edit.mp4", ".mp4")
    job_id = uuid.uuid4().hex[:12]
    music_path = None
    if music_file and music_file.filename:
        music_path = await save_upload(music_file)
        if music_path.suffix.lower() not in {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}:
            raise HTTPException(status_code=422, detail="music_file 必須是音訊檔")

    kwargs = {
        "clip_paths": [str(p) for p in clip_paths],
        "trim_specs": trims or [{} for _ in clip_paths],
        "aspect": aspect,
        "quality": quality,
        "transition": transition,
        "output_filename": out_filename,
        "fps": 24,
        "target_seconds": target_seconds if target_seconds > 0 else None,
        "music_path": str(music_path) if music_path else None,
        "original_audio_volume": original_audio_volume,
        "title_text": title_text,
        "ending_text": ending_text,
        "reuse_mode": reuse_mode,
    }
    _set_job(job_id, status="queued", job_type="editor")
    threading.Thread(target=_run_editor_job, args=(job_id, kwargs), daemon=True).start()
    return {"status": "queued", "job_id": job_id, "job_type": "editor"}


@app.get("/api/editor/jobs/{job_id}")
async def api_editor_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job.get("job_type") != "editor":
        raise HTTPException(status_code=404, detail="找不到這個剪輯任務")
    return {"job_id": job_id, **job}


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
    burn_subtitles: bool = Form(True),
    audio_file: UploadFile = File(...),
    media_files: List[UploadFile] = File(...),
):
    if not media_files:
        raise HTTPException(status_code=400, detail="至少需要一張圖片或一段影片")
    if len(media_files) > MAX_MEDIA:
        raise HTTPException(status_code=400, detail=f"一次最多 {MAX_MEDIA} 個畫面素材")
    if not 5 <= duration <= MAX_DURATION:
        raise HTTPException(status_code=422, detail=f"MV 長度必須介於 5 與 {MAX_DURATION} 秒；不會自動截短")
    if aspect not in {"9:16", "16:9"}:
        raise HTTPException(status_code=422, detail="MV 比例只支援 9:16 或 16:9")
    audio_path = await save_upload(audio_file)
    media_paths = [await save_upload(f) for f in media_files]
    out_filename = unique_name("music_video.mp4", ".mp4")
    job_id = uuid.uuid4().hex[:12]
    kwargs = {
        "media_paths": [str(p) for p in media_paths],
        "audio_path": str(audio_path),
        "title": title,
        "lyrics": lyrics,
        "duration": duration,
        "aspect": aspect,
        "output_filename": out_filename,
        "burn_subtitles": burn_subtitles,
    }
    _set_job(job_id, status="queued")
    threading.Thread(target=_run_mv_job, args=(job_id, kwargs), daemon=True).start()
    return {"status": "queued", "job_id": job_id}


@app.get("/api/mv/status/{job_id}")
async def api_mv_status(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="找不到這個任務")
    return {"job_id": job_id, **job}


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

