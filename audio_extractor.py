# -*- coding: utf-8 -*-
"""
Audio extractor / stem separator.
Uses Demucs when installed; otherwise a simple FFmpeg fallback.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path


class AudioExtractor:
    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def demucs_available(self):
        return shutil.which("demucs") is not None

    def separate_vocals(self, input_media_path: str):
        src = Path(input_media_path)
        stem = src.stem
        vocal_target = self.output_dir / f"{stem}_vocals.wav"
        accompaniment_target = self.output_dir / f"{stem}_accompaniment.wav"

        if self.demucs_available():
            temp_dir = self.output_dir / f"_demucs_{stem}"
            cmd = ["demucs", "--two-stems=vocals", "-o", str(temp_dir), str(src)]
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            expected_vocal = temp_dir / "htdemucs" / stem / "vocals.wav"
            expected_bgm = temp_dir / "htdemucs" / stem / "no_vocals.wav"
            if r.returncode == 0 and expected_vocal.exists() and expected_bgm.exists():
                shutil.move(str(expected_vocal), str(vocal_target))
                shutil.move(str(expected_bgm), str(accompaniment_target))
                shutil.rmtree(temp_dir, ignore_errors=True)
                return {"vocal_path": str(vocal_target), "accompaniment_path": str(accompaniment_target), "engine": "demucs"}

        if not shutil.which("ffmpeg"):
            raise RuntimeError("找不到 Demucs，也找不到 FFmpeg。")

        # Fallback is frequency/center processing only, not true AI stem separation.
        r1 = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-af", "highpass=f=120,lowpass=f=5200,volume=1.15", str(vocal_target)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        r2 = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-af", "stereotools=mlev=0.2:slev=1.35,volume=0.9", str(accompaniment_target)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if r1.returncode != 0 or r2.returncode != 0:
            raise RuntimeError("FFmpeg 分離 fallback 失敗。")
        return {"vocal_path": str(vocal_target), "accompaniment_path": str(accompaniment_target), "engine": "ffmpeg_fallback"}
