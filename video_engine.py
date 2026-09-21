# -*- coding: utf-8 -*-
"""
Automatic MV renderer optimized for Render Free.
One cheap ffmpeg pass for still images.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}

FFMPEG_TIMEOUT = int(os.getenv("MV_FFMPEG_TIMEOUT", "240"))
MAX_DURATION = int(os.getenv("MV_MAX_DURATION", "60"))
PRESET = os.getenv("MV_X264_PRESET", "ultrafast")
CRF = os.getenv("MV_X264_CRF", "30")
THREADS = os.getenv("MV_THREADS", "1")


class VideoEngine:
    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _require_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("找不到 FFmpeg。MV 生成功能需要 FFmpeg。")

    def _size(self, aspect, duration):
        if duration <= 15:
            return (1280, 720) if aspect == "16:9" else (720, 1280)
        return (960, 540) if aspect == "16:9" else (540, 960)

    def _fps(self, duration):
        return "24" if duration <= 15 else "12"

    def _run(self, cmd, timeout=FFMPEG_TIMEOUT):
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

    def _clean_lyric_lines(self, lyrics):
        lines = []
        for raw in (lyrics or "").splitlines():
            s = raw.strip()
            if not s or re.match(r"^[【\[].*[】\]]$", s):
                continue
            lines.append(s)
        return lines

    def _fmt_srt_time(self, seconds):
        ms = int(round(seconds * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def _write_srt(self, title, lyrics, duration, filename):
        lines = self._clean_lyric_lines(lyrics)
        if title:
            lines = [title] + lines
        if not lines:
            lines = [title or "AI Music Studio"]
        slot = max(1.2, duration / max(len(lines), 1))
        entries = []
        t = 0.0
        for i, line in enumerate(lines, 1):
            start = t
            end = min(duration, t + slot)
            entries.append(
                f"{i}\n{self._fmt_srt_time(start)} --> {self._fmt_srt_time(end)}\n{line}\n"
            )
            t += slot
            if t >= duration:
                break
        path = self.output_dir / filename
        path.write_text("\n".join(entries), encoding="utf-8")
        return path

    def _vf_fit(self, width, height, fps):
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={fps},format=yuv420p"
        )

    def render_mv(
        self,
        media_paths,
        audio_path,
        title="",
        lyrics="",
        duration=30,
        aspect="9:16",
        output_filename=None,
    ):
        self._require_ffmpeg()
        if not media_paths:
            raise RuntimeError("至少需要一張圖片或一段影片")
        if not audio_path or not Path(audio_path).exists():
            raise RuntimeError("找不到完成音訊")

        duration = max(5, min(int(duration), MAX_DURATION))
        width, height = self._size(aspect, duration)
        fps = self._fps(duration)
        job = uuid.uuid4().hex[:8]
        output_filename = output_filename or f"mv_{job}.mp4"
        final = self.output_dir / output_filename
        srt = self._write_srt(title, lyrics, duration, f"mv_{job}.srt")
        src = media_paths[0]
        ext = Path(src).suffix.lower()
        vf = self._vf_fit(width, height, fps)

        if ext in IMAGE_EXT:
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", fps, "-i", src,
                "-i", audio_path,
                "-t", str(duration),
                "-shortest",
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", PRESET,
                "-crf", CRF,
                "-tune", "stillimage",
                "-threads", THREADS,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "96k",
                "-ac", "2",
                "-ar", "44100",
                "-movflags", "+faststart",
                str(final),
            ]
        elif ext in VIDEO_EXT:
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", src,
                "-i", audio_path,
                "-t", str(duration),
                "-shortest",
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", PRESET,
                "-crf", CRF,
                "-threads", THREADS,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "96k",
                "-ac", "2",
                "-ar", "44100",
                "-movflags", "+faststart",
                str(final),
            ]
        else:
            raise RuntimeError(f"不支援的素材格式：{ext}")

        try:
            r = self._run(cmd)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"MV 編碼超時（{FFMPEG_TIMEOUT}s）。請先測 15–30 秒，或只放 1 張圖。"
            )

        if r.returncode != 0 or not final.exists():
            raise RuntimeError(
                "MV 輸出失敗：" + r.stderr.decode("utf-8", "ignore")[-260:]
            )
        return {
            "path": str(final),
            "subtitle_path": str(srt),
            "subtitles_burned": False,
            "width": width,
            "height": height,
            "fps": fps,
            "duration": duration,
        }
