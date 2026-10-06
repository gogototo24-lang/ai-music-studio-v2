# -*- coding: utf-8 -*-
"""
Automatic MV renderer optimized for lightweight Render deployments.

Features:
- Multiple image/video inputs are rendered sequentially instead of using only
  the first file.
- 9:16 and 16:9 output.
- Optional subtitle burn-in with graceful fallback to sidecar SRT.
- One normalized H.264 segment per source for reliable concat.
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
MAX_MEDIA = int(os.getenv("MV_MAX_MEDIA", "12"))
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
        return "24" if duration <= 15 else "18"

    def _run(self, cmd, timeout=FFMPEG_TIMEOUT):
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

    def _run_checked(self, cmd, label, timeout=FFMPEG_TIMEOUT):
        try:
            r = self._run(cmd, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{label}超時（{timeout}s）")
        if r.returncode != 0:
            err = r.stderr.decode("utf-8", "ignore")[-500:]
            raise RuntimeError(f"{label}失敗：{err}")
        return r

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
            f"crop={width}:{height},fps={fps},setsar=1,format=yuv420p"
        )

    def _segment_durations(self, duration, count):
        base = float(duration) / float(count)
        values = [base for _ in range(count)]
        values[-1] += float(duration) - sum(values)
        return values

    def _render_segment(self, src, seg_duration, width, height, fps, out_path):
        ext = Path(src).suffix.lower()
        vf = self._vf_fit(width, height, fps)
        common = [
            "-t", f"{seg_duration:.3f}",
            "-an",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", PRESET,
            "-crf", CRF,
            "-threads", THREADS,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out_path),
        ]
        if ext in IMAGE_EXT:
            cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", fps, "-i", src] + common
        elif ext in VIDEO_EXT:
            cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", src] + common
        else:
            raise RuntimeError(f"不支援的素材格式：{ext}")
        self._run_checked(cmd, f"素材轉碼 {Path(src).name}")

    def _concat_segments(self, segments, concat_list, video_only):
        lines = []
        for segment in segments:
            safe = str(Path(segment).resolve()).replace("'", "'\\''")
            lines.append(f"file '{safe}'")
        concat_list.write_text("\n".join(lines), encoding="utf-8")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            "-movflags", "+faststart",
            str(video_only),
        ]
        self._run_checked(cmd, "多素材串接")

    def _subtitle_filter(self, srt_path):
        escaped = str(Path(srt_path).resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        return (
            f"subtitles='{escaped}':"
            "force_style='FontName=Noto Sans CJK TC,FontSize=18,Outline=2,Shadow=1,MarginV=48'"
        )

    def _mux_final(self, video_only, audio_path, final, duration, srt, burn_subtitles):
        base = [
            "ffmpeg", "-y",
            "-i", str(video_only),
            "-i", str(audio_path),
            "-t", str(duration),
            "-map", "0:v:0",
            "-map", "1:a:0",
        ]
        if burn_subtitles:
            cmd = base + [
                "-vf", self._subtitle_filter(srt),
                "-c:v", "libx264",
                "-preset", PRESET,
                "-crf", CRF,
                "-threads", THREADS,
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "44100",
                "-movflags", "+faststart",
                str(final),
            ]
            try:
                self._run_checked(cmd, "字幕燒錄與 MV 輸出")
                return True
            except RuntimeError:
                pass

        cmd = base + [
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            "-ar", "44100",
            "-movflags", "+faststart",
            str(final),
        ]
        self._run_checked(cmd, "MV 輸出")
        return False

    def render_mv(
        self,
        media_paths,
        audio_path,
        title="",
        lyrics="",
        duration=30,
        aspect="9:16",
        output_filename=None,
        burn_subtitles=True,
    ):
        self._require_ffmpeg()
        media_paths = [str(Path(p)) for p in media_paths if p]
        if not media_paths:
            raise RuntimeError("至少需要一張圖片或一段影片")
        if len(media_paths) > MAX_MEDIA:
            raise RuntimeError(f"一次最多 {MAX_MEDIA} 個畫面素材")
        if not audio_path or not Path(audio_path).exists():
            raise RuntimeError("找不到完成音訊")

        duration = max(5, min(int(duration), MAX_DURATION))
        width, height = self._size(aspect, duration)
        fps = self._fps(duration)
        job = uuid.uuid4().hex[:8]
        output_filename = output_filename or f"mv_{job}.mp4"
        final = self.output_dir / output_filename
        srt = self._write_srt(title, lyrics, duration, f"mv_{job}.srt")
        workdir = self.output_dir / f"_mv_{job}"
        workdir.mkdir(parents=True, exist_ok=True)

        try:
            durations = self._segment_durations(duration, len(media_paths))
            segments = []
            for index, (src, seg_duration) in enumerate(zip(media_paths, durations), 1):
                segment = workdir / f"segment_{index:02}.mp4"
                self._render_segment(src, seg_duration, width, height, fps, segment)
                segments.append(segment)

            video_only = workdir / "video_only.mp4"
            concat_list = workdir / "concat.txt"
            self._concat_segments(segments, concat_list, video_only)
            subtitles_burned = self._mux_final(
                video_only,
                audio_path,
                final,
                duration,
                srt,
                bool(burn_subtitles),
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        if not final.exists():
            raise RuntimeError("MV 輸出失敗：找不到完成檔")

        return {
            "path": str(final),
            "subtitle_path": str(srt),
            "subtitles_burned": subtitles_burned,
            "width": width,
            "height": height,
            "fps": fps,
            "duration": duration,
            "media_count": len(media_paths),
        }
