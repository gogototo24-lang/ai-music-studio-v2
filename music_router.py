# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import httpx

from music_engine import MusicEngine

PROVIDERS = {
    "musicgen": {
        "name": "MusicGen Local",
        "role": "本機／GPU BGM",
        "full_song": False,
        "lyrics": False,
        "paid": False,
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

    def status(self) -> list[dict[str, Any]]:
        primary = os.getenv("MUSIC_PRIMARY_PROVIDER", "musicgen").strip().lower() or "musicgen"
        rows = []
        for key, meta in PROVIDERS.items():
            configured = (
                self.musicgen.musicgen_available()
                if key == "musicgen"
                else bool(self._url(key) and self._token())
            )
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
