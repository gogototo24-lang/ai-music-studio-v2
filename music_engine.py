# -*- coding: utf-8 -*-
"""
Local BGM engine.

Design goals:
- Prefer MusicGen when available.
- Fall back gracefully to FFmpeg demo audio.
- Expose runtime metadata for API health checks.
- Allow runtime override of model and device.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

MUSIC_STYLES = {
    "wuxia_epic": {"name": "武戲戰曲", "tags": "epic orchestral wuxia, war drums, pipa, erhu, cinematic battle, high tension, 128 bpm"},
    "wuxia_zen": {"name": "竹林文戲", "tags": "traditional Chinese ambient, guqin, bamboo flute, rain, serene strings, 74 bpm"},
    "taiwanese_rock": {"name": "台語搖滾", "tags": "Taiwanese folk rock, electric guitar, suona, energetic drums, memorable chorus, 136 bpm"},
    "tragic_ballad": {"name": "悲情宿命", "tags": "melancholy Chinese ballad, erhu, cello, piano, cinematic emotional drama, 68 bpm"},
    "dark_warlord": {"name": "魔王降世", "tags": "dark gothic wuxia, ominous choir, thunderous bass, gong, low brass, 108 bpm"},
}


class MusicEngine:
    def __init__(self, output_dir="outputs", model_name=None, device=None, allow_fallback=True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name or os.getenv("MUSICGEN_MODEL", "facebook/musicgen-small")
        self.allow_fallback = allow_fallback
        self.device = device or self.detect_device()

    def get_style_info(self, style_key):
        return MUSIC_STYLES.get(style_key, MUSIC_STYLES["wuxia_epic"])

    def detect_device(self):
        if importlib.util.find_spec("torch") is None:
            return "cpu"
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"

    def cuda_available(self):
        if importlib.util.find_spec("torch") is None:
            return False
        import torch
        return bool(torch.cuda.is_available())

    def musicgen_available(self):
        return importlib.util.find_spec("audiocraft") is not None and importlib.util.find_spec("torch") is not None

    def runtime_status(self):
        ffmpeg_ok = shutil.which("ffmpeg") is not None
        return {
            "musicgen_available": self.musicgen_available(),
            "ffmpeg_available": ffmpeg_ok,
            "cuda_available": self.cuda_available(),
            "device": self.device,
            "model_name": self.model_name,
            "fallback_enabled": self.allow_fallback,
        }

    def _generate_musicgen(self, prompt: str, duration: int, output_path: Path, model_name: str | None = None, device: str | None = None):
        if not self.musicgen_available():
            raise RuntimeError("MusicGen 不可用：未安裝 audiocraft / torch")

        from audiocraft.models import MusicGen
        import torchaudio
        import torch

        selected_model = model_name or self.model_name
        selected_device = device or self.device

        try:
            model = MusicGen.get_pretrained(selected_model)
        except Exception as exc:
            raise RuntimeError(f"MusicGen 模型載入失敗：{exc}") from exc

        try:
            model.to(selected_device)
        except Exception:
            try:
                model.to("cpu")
                selected_device = "cpu"
            except Exception:
                pass

        try:
            model.set_generation_params(duration=int(duration))
            wav = model.generate([prompt])
        except Exception as exc:
            raise RuntimeError(f"MusicGen 生成失敗：{exc}") from exc

        try:
            torchaudio.save(str(output_path), wav[0].cpu(), model.sample_rate)
        except Exception as exc:
            # Some environments may return a different tensor layout; try a second fallback.
            try:
                tensor = wav[0].detach().cpu()
                torchaudio.save(str(output_path), tensor, model.sample_rate)
            except Exception:
                raise RuntimeError(f"MusicGen 輸出儲存失敗：{exc}") from exc

        return {
            "path": str(output_path),
            "engine": "musicgen",
            "model": selected_model,
            "device": selected_device,
            "note": "MusicGen 本機生成",
        }

    def generate_local_bgm(
        self,
        prompt: str,
        duration=15,
        output_filename="bgm.wav",
        model_name: str | None = None,
        device: str | None = None,
        allow_fallback: bool | None = None,
    ):
        output_path = self.output_dir / output_filename
        selected_model = model_name or self.model_name
        selected_device = device or self.device
        fallback_enabled = self.allow_fallback if allow_fallback is None else allow_fallback

        if self.musicgen_available():
            try:
                return self._generate_musicgen(prompt, int(duration), output_path, selected_model, selected_device)
            except Exception as e:
                musicgen_error = str(e)[:180]
        else:
            musicgen_error = "未安裝 MusicGen / PyTorch"

        if not fallback_enabled:
            raise RuntimeError(f"MusicGen 不可用，且 fallback 已禁用。錯誤：{musicgen_error}")

        if not shutil.which("ffmpeg"):
            raise RuntimeError(f"MusicGen 不可用，且找不到 FFmpeg。MusicGen 狀態：{musicgen_error}")

        lavfi = (
            f"aevalsrc=0:d={duration}:s=44100[zero];"
            f"sine=f=110:d={duration}:s=44100,volume=0.11[a];"
            f"sine=f=164.81:d={duration}:s=44100,volume=0.06[b];"
            f"sine=f=220:d={duration}:s=44100,volume=0.05[c];"
            f"anoisesrc=d={duration}:c=pink:r=44100:a=0.018,lowpass=f=1000[n];"
            f"[a][b][c][n]amix=inputs=4:duration=longest,afade=t=in:st=0:d=1,afade=t=out:st={max(1,duration-1)}:d=1"
        )
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", lavfi, "-c:a", "pcm_s16le", str(output_path)]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise RuntimeError("FFmpeg demo BGM 生成失敗：" + r.stderr.decode("utf-8", "ignore")[:240])
        return {
            "path": str(output_path),
            "engine": "procedural_fallback",
            "model": selected_model,
            "device": selected_device,
            "note": f"目前是 FFmpeg 測試配樂，不是 AI 音樂。MusicGen 狀態：{musicgen_error}",
        }


if __name__ == "__main__":
    engine = MusicEngine(output_dir="outputs")
    print(engine.runtime_status())
