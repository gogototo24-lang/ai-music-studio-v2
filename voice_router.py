# -*- coding: utf-8 -*-
"""
Voice provider router.

Keep the lightweight Render service stable:
- edge: local fallback, always available
- cosyvoice: optional remote adapter
- pilottts: optional remote adapter, recommended for zh-minnan experiments
- gpt-sovits: optional official HTTP API service

Large models are intentionally NOT installed in the lite Render image.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from voice_engine import VoiceEngine, CHARACTER_PRESETS


PROVIDER_META = {
    "edge": {
        "name": "Edge TTS",
        "role": "輕量 fallback／台灣中文",
        "languages": ["zh-TW"],
        "voice_clone": False,
    },
    "cosyvoice": {
        "name": "CosyVoice 3",
        "role": "角色音色／情緒／方言主力候選",
        "languages": ["zh", "zh-minnan", "multilingual"],
        "voice_clone": True,
    },
    "pilottts": {
        "name": "PilotTTS",
        "role": "台語 zh-minnan A/B 測試首選",
        "languages": ["zh", "zh-minnan"],
        "voice_clone": True,
    },
    "gpt-sovits": {
        "name": "GPT-SoVITS",
        "role": "固定角色聲紋／few-shot",
        "languages": ["zh", "yue", "en", "ja", "ko"],
        "voice_clone": True,
    },
}


class VoiceProviderRouter:
    def __init__(self, edge_engine: VoiceEngine, output_dir: str = "outputs"):
        self.edge_engine = edge_engine
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _url(self, provider: str) -> str:
        env_map = {
            "cosyvoice": "COSYVOICE_API_URL",
            "pilottts": "PILOTTTS_API_URL",
            "gpt-sovits": "GPT_SOVITS_API_URL",
        }
        key = env_map.get(provider)
        return (os.getenv(key, "") if key else "").strip().rstrip("/")

    def provider_status(self) -> list[dict[str, Any]]:
        primary = os.getenv("VOICE_PRIMARY_PROVIDER", "edge").strip().lower() or "edge"
        items = []
        for key, meta in PROVIDER_META.items():
            configured = key == "edge" or bool(self._url(key))
            items.append({
                "key": key,
                **meta,
                "configured": configured,
                "primary": key == primary,
            })
        return items

    def _pick_provider(self, requested: str, language: str) -> str:
        requested = (requested or "auto").strip().lower()
        if requested != "auto":
            return requested

        primary = os.getenv("VOICE_PRIMARY_PROVIDER", "edge").strip().lower() or "edge"
        if primary in PROVIDER_META and (primary == "edge" or self._url(primary)):
            return primary

        # Prefer PilotTTS for Minnan only when it is explicitly configured.
        if (language or "").lower() in {"minnan", "zh-minnan", "taiwanese", "nan-tw"} and self._url("pilottts"):
            return "pilottts"
        return "edge"

    async def _save_response_audio(self, response: httpx.Response, filename_stem: str) -> str:
        content_type = response.headers.get("content-type", "").lower()
        ext = ".wav"
        if "mpeg" in content_type or "mp3" in content_type:
            ext = ".mp3"
        elif "ogg" in content_type:
            ext = ".ogg"
        elif "aac" in content_type:
            ext = ".aac"
        output = self.output_dir / f"{filename_stem}{ext}"
        output.write_bytes(response.content)
        if output.stat().st_size < 128:
            output.unlink(missing_ok=True)
            raise RuntimeError("遠端聲線服務回傳的音訊太小或為空")
        return str(output)

    async def _remote_standard(
        self,
        provider: str,
        text: str,
        preset: str,
        language: str,
        emotion: str,
        reference_id: str,
        filename_stem: str,
    ) -> str:
        base = self._url(provider)
        if not base:
            raise RuntimeError(f"{PROVIDER_META[provider]['name']} 尚未設定 API URL")

        payload = {
            "text": text,
            "preset": preset,
            "language": language,
            "emotion": emotion,
            "reference_id": reference_id,
        }
        timeout = httpx.Timeout(120.0, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{base}/synthesize", json=payload)
        if response.status_code >= 400:
            detail = response.text[:400]
            raise RuntimeError(f"{PROVIDER_META[provider]['name']} 失敗：HTTP {response.status_code} {detail}")
        return await self._save_response_audio(response, filename_stem)

    async def _gpt_sovits(
        self,
        text: str,
        language: str,
        filename_stem: str,
    ) -> str:
        base = self._url("gpt-sovits")
        if not base:
            raise RuntimeError("GPT-SoVITS 尚未設定 API URL")

        lang = (language or "zh").lower()
        lang_map = {
            "zh-tw": "zh",
            "zh": "zh",
            "mandarin": "zh",
            "yue": "yue",
            "en": "en",
            "ja": "ja",
            "ko": "ko",
        }
        if lang not in lang_map:
            raise RuntimeError("GPT-SoVITS 這條路徑目前不作台語／閩南語主力，請改用 PilotTTS 或 CosyVoice")
        payload = {"text": text, "text_language": lang_map[lang]}
        timeout = httpx.Timeout(120.0, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(base + "/", json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"GPT-SoVITS 失敗：HTTP {response.status_code} {response.text[:400]}")
        return await self._save_response_audio(response, filename_stem)

    async def generate(
        self,
        *,
        text: str,
        preset: str = "heroine",
        provider: str = "auto",
        language: str = "zh-TW",
        emotion: str = "neutral",
        reference_id: str = "",
        enable_reverb: bool = True,
        filename_stem: str = "voice",
    ) -> dict[str, Any]:
        selected = self._pick_provider(provider, language)
        if selected not in PROVIDER_META:
            raise RuntimeError(f"未知聲線 provider：{selected}")

        if selected == "edge":
            if preset not in CHARACTER_PRESETS:
                raise RuntimeError(f"未知聲線 preset：{preset}")
            output = await self.edge_engine.generate_voice(
                text=text,
                preset_key=preset,
                enable_reverb=enable_reverb,
                filename=f"{filename_stem}.mp3",
            )
        elif selected == "gpt-sovits":
            output = await self._gpt_sovits(text, language, filename_stem)
        else:
            output = await self._remote_standard(
                selected, text, preset, language, emotion, reference_id, filename_stem
            )

        return {
            "path": output,
            "provider": selected,
            "provider_name": PROVIDER_META[selected]["name"],
            "language": language,
            "emotion": emotion,
        }
