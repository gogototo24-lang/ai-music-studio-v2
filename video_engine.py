# -*- coding: utf-8 -*-
"""
Automatic MV renderer optimized for Render Free.
Long jobs must finish in one cheap ffmpeg pass.
Subtitle burn-in is optional and never fails the whole MV.
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
BURN_SUBS = os.getenv("MV_BURN_SUBS", "0") == "1"


class VideoEngine:
    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _require_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("找不到 FFmpeg。MV 生成功能需要 FFmpeg。")

    def _size(self, aspect, duration):
        # Longer clips use a smaller frame so encode stays under proxy limits.
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
        slot = max(1.2, duration / len(lines))
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

    def _encode_v(self):
        return [
            "-c:v", "libx264",
            "-preset", PRESET,
            "-crf", CRF,
            "-tune", "stillimage",
            "-threads", THREADS,
            "-pix_fmt", "yuv420p",
        ]

    def _encode_a(self):
        return ["-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "44100"]

    def _one_pass_still(self, image, audio_path, duration, width, height, fps, final, srt):
        vf = self._vf_fit(width, height, fps)
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", fps, "-i", image,
            "-i", audio_path,
            "-t", str(duration),
            "-shortest",
            "-vf", vf,
            *self._encode_v(),
            *self._encode_a(),
            "-movflags", "+faststart",
            str(final),
        ]
        if BURN_SUBS:
            escaped = str(srt).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
            cmd_sub = cmd.copy()
            cmd_sub[cmd_sub.index("-vf") + 1] = (
                vf + f",subtitles='{escaped}':force_style='FontSize=16,Alignment=2,MarginV=50'"
            )
            try:
                r = self._run(cmd_sub)
                if r.returncode == 0 and Path(final).exists():
                    return r, True
            except subprocess.TimeoutExpired:
                if Path(final).exists():
                    Path(final).unlink(missing_ok=True)
        r = self._run(cmd)
        return r, False

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

        try:
            only_images = all(Path(p).suffix.lower() in IMAGE_EXT for p in media_paths)
            if only_images:
                r, burned = self._one_pass_still(
                    media_paths[0], audio_path, duration, width, height, fps, final, srt
                )
            else:
                vf = self._vf_fit(width, height, fps)
                cmd = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", media_paths[0],
                    "-i", audio_path,
                    "-t", str(duration),
                    "-shortest",
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
                    "-threads", THREADS, "-pix_fmt", "yuv420p",
                    *self._encode_a(),
                    "-movflags", "+faststart",
                    str(final),
                ]
                r = self._run(cmd)
                burned = False

            if r.returncode != 0 or not final.exists():
                raise RuntimeError(
                    "MV 輸出失敗：" + r.stderr.decode("utf-8", "ignore")[-260:]
                )
            return {
                "path": str(final),
                "subtitle_path": str(srt),
                "subtitles_burned": burned,
                "width": width,
                "height": height,
                "fps": fps,
                "duration": duration,
            }
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"MV 編碼超時（{FFMPEG_TIMEOUT}s）。請先測 15–30 秒，或只放 1 張圖。"
            )
    def _require_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("找不到 FFmpeg。MV 生成功能需要 FFmpeg。")

    def _size(self, aspect):
        # 720p-class instead of 1080p to survive Render Free CPU/RAM/timeout.
        return (1280, 720) if aspect == "16:9" else (720, 1280)

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
        slot = max(1.2, duration / len(lines))
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

    def _encode_args(self):
        return [
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
        ]

    def _vf_fit(self, width, height):
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={FPS},format=yuv420p"
        )

    def _render_segment(self, media, seconds, width, height, target):
        ext = Path(media).suffix.lower()
        vf = self._vf_fit(width, height)
        if ext in IMAGE_EXT:
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", FPS, "-i", media,
                "-t", f"{seconds:.3f}",
                "-vf", vf, "-an",
                "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
                "-threads", THREADS, "-pix_fmt", "yuv420p",
                str(target),
            ]
        elif ext in VIDEO_EXT:
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", media,
                "-t", f"{seconds:.3f}",
                "-vf", vf, "-an",
                "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
                "-threads", THREADS, "-pix_fmt", "yuv420p",
                str(target),
            ]
        else:
            raise RuntimeError(f"不支援的素材格式：{ext}")
        r = self._run(cmd)
        if r.returncode != 0 or not Path(target).exists():
            raise RuntimeError(
                "片段編碼失敗：" + r.stderr.decode("utf-8", "ignore")[-250:]
            )

    def _mux_with_optional_subs(self, base_video, audio_path, srt, duration, final):
        escaped = str(srt).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        vf = (
            f"subtitles='{escaped}':"
            "force_style='FontName=Noto Sans CJK TC,FontSize=16,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=60'"
        )
        cmd_sub = [
            "ffmpeg", "-y",
            "-i", str(base_video),
            "-i", audio_path,
            "-vf", vf,
            "-t", str(duration),
            "-shortest",
            *self._encode_args(),
            str(final),
        ]
        try:
            r = self._run(cmd_sub)
        except subprocess.TimeoutExpired:
            r = None

        if r is None or r.returncode != 0 or not Path(final).exists():
            # 字幕燒錄失敗時自動退回無燒錄字幕版本，不要整支 MV 失敗。
            if Path(final).exists():
                Path(final).unlink(missing_ok=True)
            cmd_plain = [
                "ffmpeg", "-y",
                "-i", str(base_video),
                "-i", audio_path,
                "-t", str(duration),
                "-shortest",
                *self._encode_args(),
                str(final),
            ]
            r = self._run(cmd_plain)
            return r, False
        return r, True

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
        width, height = self._size(aspect)
        job = uuid.uuid4().hex[:8]
        output_filename = output_filename or f"mv_{job}.mp4"

        temp = self.output_dir / f"_tmp_{job}"
        temp.mkdir(parents=True, exist_ok=True)

        try:
            # Fast path: single still image — one ffmpeg pass, no concat.
            only_images = all(Path(p).suffix.lower() in IMAGE_EXT for p in media_paths)
            if only_images and len(media_paths) == 1:
                base_video = temp / "base.mp4"
                self._render_segment(media_paths[0], duration, width, height, base_video)
            else:
                seg_seconds = max(1.5, float(duration) / len(media_paths))
                segments = []
                for idx, media in enumerate(media_paths):
                    seg = temp / f"seg_{idx:03}.mp4"
                    self._render_segment(media, seg_seconds, width, height, seg)
                    segments.append(seg)

                concat_file = temp / "concat.txt"
                concat_file.write_text(
                    "\n".join([f"file '{p.as_posix()}'" for p in segments]),
                    encoding="utf-8",
                )
                base_video = temp / "base.mp4"
                r = self._run(
                    [
                        "ffmpeg", "-y",
                        "-f", "concat", "-safe", "0",
                        "-i", str(concat_file),
                        "-c:v", "copy",
                        "-t", str(duration),
                        str(base_video),
                    ]
                )
                if r.returncode != 0:
                    raise RuntimeError(
                        "MV 串接失敗：" + r.stderr.decode("utf-8", "ignore")[-250:]
                    )

            srt = self._write_srt(title, lyrics, duration, f"mv_{job}.srt")
            final = self.output_dir / output_filename
            r, burned = self._mux_with_optional_subs(
                base_video, audio_path, srt, duration, final
            )
            if r.returncode != 0 or not final.exists():
                raise RuntimeError(
                    "MV 輸出失敗：" + r.stderr.decode("utf-8", "ignore")[-260:]
                )
            return {
                "path": str(final),
                "subtitle_path": str(srt),
                "subtitles_burned": burned,
            }
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"MV 編碼超時（{FFMPEG_TIMEOUT}s）。請把秒數降到 10–15，或只放 1 張圖。"
            )
        finally:
            shutil.rmtree(temp, ignore_errors=True)
