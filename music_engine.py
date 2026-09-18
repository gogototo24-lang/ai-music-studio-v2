# -*- coding: utf-8 -*-
"""
Local BGM engine.
Tries MusicGen when installed; otherwise creates a procedural FFmpeg demo bed.
"""
from __future__ import annotations
import importlib.util
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
    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_style_info(self, style_key):
        return MUSIC_STYLES.get(style_key, MUSIC_STYLES["wuxia_epic"])

    def musicgen_available(self):
        return importlib.util.find_spec("audiocraft") is not None and importlib.util.find_spec("torch") is not None

    def generate_local_bgm(self, prompt: str, duration=15, output_filename="bgm.wav"):
        output_path = self.output_dir / output_filename

        if self.musicgen_available():
            try:
                from audiocraft.models import MusicGen
                import torchaudio
                model = MusicGen.get_pretrained("facebook/musicgen-small")
                model.set_generation_params(duration=int(duration))
                wav = model.generate([prompt])
                torchaudio.save(str(output_path), wav[0].cpu(), model.sample_rate)
                return {"path": str(output_path), "engine": "musicgen", "note": "MusicGen 本機生成"}
            except Exception as e:
                musicgen_error = str(e)[:180]
        else:
            musicgen_error = "未安裝 MusicGen / PyTorch"

        if not shutil.which("ffmpeg"):
            raise RuntimeError(f"MusicGen 不可用，且找不到 FFmpeg。MusicGen 狀態：{musicgen_error}")

        # Procedural fallback is intentionally marked as demo audio, not AI music.
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
            "note": f"目前是 FFmpeg 測試配樂，不是 AI 音樂。MusicGen 狀態：{musicgen_error}",
        }
