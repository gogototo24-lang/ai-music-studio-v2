# -*- coding: utf-8 -*-
"""
Automatic MV renderer:
- images and/or video clips
- 9:16 or 16:9
- auto timing
- burned subtitles from lyrics
- final H.264 + AAC MP4
This module edits supplied media; it does not generate new animated footage.
"""
from __future__ import annotations
import math
import re
import shutil
import subprocess
import uuid
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}


class VideoEngine:
    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _require_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("找不到 FFmpeg。MV 生成功能需要 FFmpeg。")

    def _size(self, aspect):
        return (1920, 1080) if aspect == "16:9" else (1080, 1920)

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
        slot = max(1.2, duration / len(lines))
        entries = []
        t = 0.0
        for i, line in enumerate(lines, 1):
            start = t
            end = min(duration, t + slot)
            entries.append(f"{i}\n{self._fmt_srt_time(start)} --> {self._fmt_srt_time(end)}\n{line}\n")
            t += slot
            if t >= duration:
                break
        path = self.output_dir / filename
        path.write_text("\n".join(entries), encoding="utf-8")
        return path

    def _render_segment(self, media, seconds, width, height, target):
        ext = Path(media).suffix.lower()
        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=30,format=yuv420p"
        if ext in IMAGE_EXT:
            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", media, "-t", f"{seconds:.3f}",
                "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-pix_fmt", "yuv420p", str(target),
            ]
        elif ext in VIDEO_EXT:
            cmd = [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", media, "-t", f"{seconds:.3f}",
                "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-pix_fmt", "yuv420p", str(target),
            ]
        else:
            raise RuntimeError(f"MV 不支援此媒體格式：{ext}")
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise RuntimeError("片段轉檔失敗：" + r.stderr.decode("utf-8", "ignore")[:250])

    def render_mv(self, media_paths, audio_path, title="", lyrics="", duration=30, aspect="9:16", output_filename="music_video.mp4"):
        self._require_ffmpeg()
        width, height = self._size(aspect)
        media_paths = [str(x) for x in media_paths if Path(x).suffix.lower() in IMAGE_EXT | VIDEO_EXT]
        if not media_paths:
            raise RuntimeError("沒有可用的圖片或影片素材。")

        job = uuid.uuid4().hex[:10]
        temp = self.output_dir / f"_mv_{job}"
        temp.mkdir(parents=True, exist_ok=True)
        seg_seconds = max(1.5, float(duration) / len(media_paths))
        segments = []
        for idx, media in enumerate(media_paths):
            seg = temp / f"seg_{idx:03}.mp4"
            self._render_segment(media, seg_seconds, width, height, seg)
            segments.append(seg)

        concat_file = temp / "concat.txt"
        concat_file.write_text("\n".join([f"file '{p.as_posix()}'" for p in segments]), encoding="utf-8")
        base_video = temp / "base.mp4"
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
             "-c:v", "copy", "-t", str(duration), str(base_video)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if r.returncode != 0:
            raise RuntimeError("MV 串接失敗：" + r.stderr.decode("utf-8", "ignore")[:250])

        srt = self._write_srt(title, lyrics, duration, f"mv_{job}.srt")
        final = self.output_dir / output_filename

        # Use subtitles filter when available; if it fails, retry without burned subtitles.
        escaped = str(srt).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        vf = (
            f"subtitles='{escaped}':"
            "force_style='FontName=Noto Sans CJK TC,FontSize=18,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=80'"
        )
        cmd = [
            "ffmpeg", "-y", "-i", str(base_video), "-i", audio_path,
            "-vf", vf, "-t", str(duration), "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final),
        ]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            cmd = [
                "ffmpeg", "-y", "-i", str(base_video), "-i", audio_path,
                "-t", str(duration), "-shortest",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final),
            ]
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        shutil.rmtree(temp, ignore_errors=True)
        if r.returncode != 0 or not final.exists():
            raise RuntimeError("MV 輸出失敗：" + r.stderr.decode("utf-8", "ignore")[:260])
        return {"path": str(final), "subtitle_path": str(srt)}
