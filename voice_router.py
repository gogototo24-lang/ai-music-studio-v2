# -*- coding: utf-8 -*-
"""
Voice provider router.

Integration-safe behavior:
- /api/voice/generate stays the single stable entry point for n8n.
- auto prefers configured self-hosted / remote providers before Edge.
- a provider failure can fall through to the next configured provider.
- Edge remains the last fallback for zh-TW preview use.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from voice_engine import VoiceEngine, CHARACTER_PRESETS
from providers.runninghub_voice_adapter import RunningHubVoiceAdapter


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
    "runninghub": {
        "name": "RunningHub GPU Voice",
        "role": "RunningHub Qwen3 TTS／聲線工作流主力",
        "languages": ["zh-TW", "zh", "zh-minnan", "multilingual"],
        "voice_clone": True,
    },
}


class VoiceProviderRouter:
    def __init__(self, edge_engine: VoiceEngine, output_dir: str = "outputs"):
        self.edge_engine = edge_engine
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.runninghub = RunningHubVoiceAdapter(output_dir=str(self.output_dir))

    def _url(self, provider: str) -> str:
        env_map = {
            "cosyvoice": "COSYVOICE_API_URL",
            "pilottts": "PILOTTTS_API_URL",
            "gpt-sovits": "GPT_SOVITS_API_URL",
        }
        key = env_map.get(provider)
        return (os.getenv(key, "") if key else "").strip().rstrip("/")

    def _configured(self, provider: str) -> bool:
        if provider == "runninghub":
            return self.runninghub.configured()
        return provider == "edge" or bool(self._url(provider))

    def provider_status(self) -> list[dict[str, Any]]:
        primary = os.getenv("VOICE_PRIMARY_PROVIDER", "").strip().lower() or "auto"
        items = []
        for key, meta in PROVIDER_META.items():
            items.append({
                "key": key,
                **meta,
                "configured": self._configured(key),
                "primary": key == primary,
            })
        return items

    def _provider_candidates(self, requested: str, language: str) -> list[str]:
        requested = (requested or "auto").strip().lower()
        lang = (language or "").strip().lower()
        is_minnan = lang in {"minnan", "zh-minnan", "taiwanese", "nan-tw"}

        if requested != "auto" and requested not in PROVIDER_META:
            raise RuntimeError(f"未知聲線 provider：{requested}")

        # Optional explicit fallback order, e.g.
        # VOICE_FALLBACK_ORDER=pilottts,cosyvoice,gpt-sovits,edge
        custom = [
            p.strip().lower()
            for p in os.getenv("VOICE_FALLBACK_ORDER", "").split(",")
            if p.strip()
        ]
        custom = [p for p in custom if p in PROVIDER_META]

        if custom:
            base = custom
        elif is_minnan:
            # GPT-SoVITS is intentionally not in the default Minnan route.
            base = ["pilottts", "cosyvoice", "edge"]
        else:
            # Prefer configured character-voice services, keep Edge last.
            base = ["runninghub", "cosyvoice", "gpt-sovits", "pilottts", "edge"]

        explicit_primary = os.getenv("VOICE_PRIMARY_PROVIDER", "").strip().lower()
        if explicit_primary in PROVIDER_META:
            base = [explicit_primary] + base

        if requested != "auto":
            base = [requested] + base

        seen = set()
        candidates = []
        for provider in base:
            if provider in seen:
                continue
            seen.add(provider)
            if self._configured(provider):
                candidates.append(provider)

        # Edge is always available as the final compatibility fallback.
        if "edge" not in seen:
            candidates.append("edge")

        return candidates

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
            raise RuntimeError(
                f"{PROVIDER_META[provider]['name']} 失敗：HTTP {response.status_code} {detail}"
            )
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
            raise RuntimeError(
                "GPT-SoVITS 這條路徑目前不作台語／閩南語主力，請改用 PilotTTS 或 CosyVoice"
            )
        payload = {"text": text, "text_language": lang_map[lang]}
        timeout = httpx.Timeout(120.0, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(base + "/", json=payload)
        if response.status_code >= 400:
            raise RuntimeError(
                f"GPT-SoVITS 失敗：HTTP {response.status_code} {response.text[:400]}"
            )
        return await self._save_response_audio(response, filename_stem)

    async def _generate_with_provider(
        self,
        provider: str,
        *,
        text: str,
        preset: str,
        language: str,
        emotion: str,
        reference_id: str,
        enable_reverb: bool,
        filename_stem: str,
    ) -> str:
        if provider == "edge":
            if preset not in CHARACTER_PRESETS:
                raise RuntimeError(f"未知聲線 preset：{preset}")
            return await self.edge_engine.generate_voice(
                text=text,
                preset_key=preset,
                enable_reverb=enable_reverb,
                filename=f"{filename_stem}.mp3",
            )
        if provider == "runninghub":
            return await self.runninghub.generate(text=text, filename_stem=filename_stem, preset=preset, language=language, emotion=emotion)
        if provider == "gpt-sovits":
            return await self._gpt_sovits(text, language, filename_stem)
        return await self._remote_standard(
            provider,
            text,
            preset,
            language,
            emotion,
            reference_id,
            filename_stem,
        )

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
        candidates = self._provider_candidates(provider, language)
        errors: list[str] = []

        for index, selected in enumerate(candidates):
            try:
                output = await self._generate_with_provider(
                    selected,
                    text=text,
                    preset=preset,
                    language=language,
                    emotion=emotion,
                    reference_id=reference_id,
                    enable_reverb=enable_reverb,
                    filename_stem=filename_stem,
                )
                return {
                    "path": output,
                    "provider": selected,
                    "provider_name": PROVIDER_META[selected]["name"],
                    "language": language,
                    "emotion": emotion,
                    "fallback_used": index > 0,
                    "attempted_providers": candidates[: index + 1],
                }
            except Exception as exc:
                errors.append(f"{selected}: {exc}")

        raise RuntimeError(
            "所有可用聲線 provider 都失敗：" + " | ".join(errors)
        )
