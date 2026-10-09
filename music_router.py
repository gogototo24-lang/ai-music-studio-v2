# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import uuid
import base64
import asyncio
from pathlib import Path
from typing import Any

import httpx

from music_engine import MusicEngine

PROVIDERS = {
    "musicgen": {
        "name": "MusicGen / Local BGM",
        "role": "本機 BGM；MusicGen 不可用時可退回 FFmpeg 測試配樂",
        "full_song": False,
        "lyrics": False,
        "paid": False,
    },
    "runpod-yue2": {
        "name": "YuE2 on RunPod Serverless",
        "role": "完整歌曲＋歌詞＋人聲；按秒 GPU 計費",
        "full_song": True,
        "lyrics": True,
        "paid": True,
    },
    "yue2": {
        "name": "YuE2 Self-hosted",
        "role": "完整歌曲＋歌詞＋人聲",
        "full_song": True,
        "lyrics": True,
        "paid": False,
    },
    "ace-step": {
        "name": "ACE-Step Self-hosted",
        "role": "快速歌曲／音樂生成候選",
        "full_song": True,
        "lyrics": True,
        "paid": False,
    },
}


class MusicProviderRouter:
    def __init__(self, musicgen: MusicEngine, output_dir: str = "outputs"):
        self.musicgen = musicgen
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _url(self, provider: str) -> str:
        key = {
            "yue2": "YUE2_API_URL",
            "ace-step": "ACESTEP_API_URL",
        }.get(provider)
        return (os.getenv(key, "") if key else "").strip().rstrip("/")

    def _token(self) -> str:
        return os.getenv("MUSIC_SERVICE_TOKEN", "").strip()

    def _runpod_configured(self) -> bool:
        return bool(
            os.getenv("RUNPOD_API_KEY", "").strip()
            and os.getenv("RUNPOD_ENDPOINT_ID", "").strip()
        )

    def status(self) -> list[dict[str, Any]]:
        primary = os.getenv("MUSIC_PRIMARY_PROVIDER", "musicgen").strip().lower() or "musicgen"
        rows = []
        for key, meta in PROVIDERS.items():
            if key == "musicgen":
                configured = self.musicgen.musicgen_available() or self.musicgen.runtime_status()["ffmpeg_available"]
            elif key == "runpod-yue2":
                configured = self._runpod_configured()
            else:
                configured = bool(self._url(key) and self._token())
            rows.append({
                "key": key,
                **meta,
                "configured": configured,
                "primary": key == primary,
            })
        return rows

    def pick(self, requested: str, *, has_lyrics: bool) -> str:
        requested = (requested or "auto").strip().lower()
        if requested != "auto":
            return requested

        primary = os.getenv("MUSIC_PRIMARY_PROVIDER", "").strip().lower()
        if primary in PROVIDERS:
            if primary == "musicgen" and self.musicgen.musicgen_available():
                return primary
            if primary != "musicgen" and self._url(primary):
                return primary

        if has_lyrics and self._runpod_configured():
            return "runpod-yue2"
        if has_lyrics and self._url("yue2"):
            return "yue2"
        if has_lyrics and self._url("ace-step"):
            return "ace-step"
        return "musicgen"

    async def _remote(
        self,
        provider: str,
        *,
        style: str,
        prompt: str,
        lyrics: str,
        duration: int,
        seed: int | None,
        title: str,
    ) -> dict[str, Any]:
        base = self._url(provider)
        if not base:
            raise RuntimeError(f"{PROVIDERS[provider]['name']} 尚未設定 API URL")

        payload = {
            "title": title,
            "style": style,
            "prompt": prompt,
            "lyrics": lyrics,
            "duration": duration,
            "seed": seed,
        }
        token = self._token()
        if not token:
            raise RuntimeError("MUSIC_SERVICE_TOKEN 尚未設定")
        timeout = httpx.Timeout(600.0, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base}/synthesize",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"{PROVIDERS[provider]['name']} 失敗：HTTP {response.status_code} "
                + response.text[:400]
            )

        content_type = response.headers.get("content-type", "audio/wav").lower()
        suffix = ".wav"
        if "flac" in content_type:
            suffix = ".flac"
        elif "mpeg" in content_type or "mp3" in content_type:
            suffix = ".mp3"

        out = self.output_dir / f"song_{provider}_{uuid.uuid4().hex[:10]}{suffix}"
        out.write_bytes(response.content)
        if out.stat().st_size < 1024:
            out.unlink(missing_ok=True)
            raise RuntimeError(f"{PROVIDERS[provider]['name']} 回傳音訊過小或為空")

        return {
            "path": str(out),
            "engine": provider,
            "provider_name": PROVIDERS[provider]["name"],
            "full_song": PROVIDERS[provider]["full_song"],
            "lyrics_supported": PROVIDERS[provider]["lyrics"],
            "note": "自架歌曲引擎生成",
        }

    async def _runpod_yue2(
        self,
        *,
        style: str,
        prompt: str,
        lyrics: str,
        duration: int,
        seed: int | None,
        title: str,
    ) -> dict[str, Any]:
        api_key = os.getenv("RUNPOD_API_KEY", "").strip()
        endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "").strip()
        if not api_key or not endpoint_id:
            raise RuntimeError("RunPod 尚未設定 RUNPOD_API_KEY / RUNPOD_ENDPOINT_ID")

        base = os.getenv("RUNPOD_API_BASE_URL", "https://api.runpod.ai/v2").rstrip("/")
        poll_seconds = max(2.0, float(os.getenv("RUNPOD_POLL_SECONDS", "4")))
        timeout_seconds = max(60, int(os.getenv("RUNPOD_TIMEOUT_SECONDS", "900")))
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "input": {
                "title": title,
                "style": style,
                "prompt": prompt,
                "lyrics": lyrics,
                "duration": int(duration),
                "seed": seed,
                "output_format": "flac",
            }
        }

        timeout = httpx.Timeout(45.0, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            created = await client.post(
                f"{base}/{endpoint_id}/run",
                headers=headers,
                json=payload,
            )
            if created.status_code >= 400:
                raise RuntimeError(
                    f"RunPod 建立任務失敗：HTTP {created.status_code} {created.text[:300]}"
                )
            created_json = created.json()
            job_id = str(created_json.get("id") or "").strip()
            if not job_id:
                raise RuntimeError("RunPod 未回傳 job id")

            elapsed = 0.0
            result = None
            while elapsed < timeout_seconds:
                await asyncio.sleep(poll_seconds)
                elapsed += poll_seconds
                status_resp = await client.get(
                    f"{base}/{endpoint_id}/status/{job_id}",
                    headers=headers,
                )
                if status_resp.status_code >= 400:
                    raise RuntimeError(
                        f"RunPod 查詢失敗：HTTP {status_resp.status_code} {status_resp.text[:300]}"
                    )
                result = status_resp.json()
                status = str(result.get("status") or "").upper()
                if status == "COMPLETED":
                    break
                if status in {"FAILED", "TIMED_OUT", "CANCELLED"}:
                    raise RuntimeError(
                        f"RunPod 任務失敗：{status} {str(result.get('error') or '')[:300]}"
                    )
            else:
                raise RuntimeError("RunPod 任務等待逾時；未自動重送，避免重複 GPU 計費")

        output = (result or {}).get("output")
        if isinstance(output, list) and output:
            output = output[0]
        if not isinstance(output, dict):
            raise RuntimeError("RunPod 完成但沒有合法 output")

        encoded = str(output.get("audio_base64") or "")
        if not encoded:
            raise RuntimeError("RunPod 完成但沒有 audio_base64")
        try:
            audio = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise RuntimeError(f"RunPod 音訊 base64 解碼失敗：{exc}") from exc
        if len(audio) < 1024:
            raise RuntimeError("RunPod 回傳音訊過小")

        fmt = str(output.get("format") or "flac").lower()
        suffix = ".flac" if fmt == "flac" else ".wav"
        out = self.output_dir / f"song_runpod_yue2_{uuid.uuid4().hex[:10]}{suffix}"
        out.write_bytes(audio)

        return {
            "path": str(out),
            "engine": "runpod-yue2",
            "provider_name": PROVIDERS["runpod-yue2"]["name"],
            "full_song": True,
            "lyrics_supported": True,
            "note": f"RunPod Serverless YuE2 完成；job={job_id}",
            "provider_job_id": job_id,
            "execution_ms": (result or {}).get("executionTime"),
            "delay_ms": (result or {}).get("delayTime"),
        }

    async def generate(
        self,
        *,
        provider: str = "auto",
        style: str = "wuxia_epic",
        prompt: str = "",
        lyrics: str = "",
        duration: int = 30,
        seed: int | None = None,
        title: str = "",
        use_fallback: bool = True,
    ) -> dict[str, Any]:
        selected = self.pick(provider, has_lyrics=bool(lyrics.strip()))
        if selected not in PROVIDERS:
            raise RuntimeError(f"未知音樂 provider：{selected}")

        if selected == "runpod-yue2":
            return await self._runpod_yue2(
                style=style,
                prompt=prompt,
                lyrics=lyrics,
                duration=duration,
                seed=seed,
                title=title,
            )

        if selected == "musicgen":
            if lyrics.strip():
                note = "MusicGen 不會唱指定歌詞；本次只生成 BGM。完整歌曲請使用 YuE2 / ACE-Step。"
            else:
                note = "MusicGen 本機 BGM。"
            style_info = self.musicgen.get_style_info(style)
            text_prompt = prompt.strip() or style_info["tags"]
            result = self.musicgen.generate_local_bgm(
                prompt=text_prompt,
                duration=duration,
                output_filename=f"bgm_{uuid.uuid4().hex[:10]}.wav",
                allow_fallback=use_fallback,
            )
            return {
                **result,
                "provider_name": PROVIDERS[selected]["name"],
                "full_song": False,
                "lyrics_supported": False,
                "note": note + " " + result.get("note", ""),
            }

        return await self._remote(
            selected,
            style=style,
            prompt=prompt,
            lyrics=lyrics,
            duration=duration,
            seed=seed,
            title=title,
        )
