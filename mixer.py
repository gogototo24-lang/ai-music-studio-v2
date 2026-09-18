# -*- coding: utf-8 -*-
"""
Multi-track mixer with real side-chain ducking when supported by FFmpeg.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path


class AudioMixer:
    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def mix(self, voice_path: str, bgm_path: str, output_filename="mix.mp3", bgm_volume=0.38, voice_delay_ms=900, ducking=True):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("找不到 FFmpeg。")

        output_path = self.output_dir / output_filename
        if ducking:
            fc = (
                f"[0:a]volume={bgm_volume}[bgm];"
                f"[1:a]adelay={voice_delay_ms}|{voice_delay_ms},volume=1.12[voice];"
                f"[bgm][voice]sidechaincompress=threshold=0.025:ratio=7:attack=18:release=260[ducked];"
                f"[ducked][voice]amix=inputs=2:duration=longest:dropout_transition=2,alimiter=limit=0.95[out]"
            )
            engine = "sidechain_ducking"
        else:
            fc = (
                f"[0:a]volume={bgm_volume}[bgm];"
                f"[1:a]adelay={voice_delay_ms}|{voice_delay_ms},volume=1.12[voice];"
                f"[bgm][voice]amix=inputs=2:duration=longest:dropout_transition=2,alimiter=limit=0.95[out]"
            )
            engine = "simple_mix"

        cmd = [
            "ffmpeg", "-y",
            "-i", bgm_path,
            "-i", voice_path,
            "-filter_complex", fc,
            "-map", "[out]",
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(output_path),
        ]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0 and ducking:
            return self.mix(voice_path, bgm_path, output_filename, bgm_volume, voice_delay_ms, ducking=False)
        if r.returncode != 0:
            raise RuntimeError("FFmpeg 混音失敗：" + r.stderr.decode("utf-8", "ignore")[:250])
        return {"path": str(output_path), "engine": engine}
