# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path


class EditorEngine:
    """FFmpeg editor for CatPaw clips. v0.2 adds music + target-duration assembly."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _probe(self, path: str) -> dict:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=codec_type",
            "-of", "json", str(path),
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"ffprobe 失敗：{Path(path).name}")
        data = json.loads(p.stdout or "{}")
        duration = float((data.get("format") or {}).get("duration") or 0)
        has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
        if duration <= 0:
            raise RuntimeError(f"讀不到媒體長度：{Path(path).name}")
        return {"duration": duration, "has_audio": has_audio}

    def probe_media(self, path: str) -> dict:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels",
            "-of", "json", str(path),
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"ffprobe 失敗：{Path(path).name}")
        data = json.loads(p.stdout or "{}")
        fmt = data.get("format") or {}
        streams = data.get("streams") or []
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

        def fps_value(raw):
            if not raw or raw in {"0/0", "N/A"}:
                return 0.0
            try:
                a, b = str(raw).split("/", 1)
                return round(float(a) / float(b), 3) if float(b) else 0.0
            except Exception:
                try:
                    return round(float(raw), 3)
                except Exception:
                    return 0.0

        return {
            "duration": round(float(fmt.get("duration") or 0), 3),
            "size_bytes": int(fmt.get("size") or 0),
            "bit_rate": int(fmt.get("bit_rate") or 0),
            "has_video": bool(video),
            "has_audio": bool(audio),
            "video_codec": video.get("codec_name") if video else None,
            "width": int(video.get("width") or 0) if video else 0,
            "height": int(video.get("height") or 0) if video else 0,
            "fps": fps_value((video or {}).get("avg_frame_rate") or (video or {}).get("r_frame_rate")),
            "audio_codec": audio.get("codec_name") if audio else None,
            "sample_rate": int(audio.get("sample_rate") or 0) if audio and str(audio.get("sample_rate") or "").isdigit() else 0,
            "channels": int(audio.get("channels") or 0) if audio else 0,
        }

    @staticmethod
    def _size(aspect: str, quality: str) -> tuple[int, int]:
        if aspect == "16:9":
            return (1920, 1080) if quality == "1080p" else (1280, 720)
        return (1080, 1920) if quality == "1080p" else (720, 1280)

    def _fontfile(self) -> str | None:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ]
        for p in candidates:
            if Path(p).exists():
                return p
        return None

    @staticmethod
    def _escape_drawtext(text: str) -> str:
        return (
            (text or "")
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace("%", "\\%")
            .replace("\n", " ")
        )

    def _normalize_segment(
        self,
        source: str,
        start: float,
        end: float,
        target: Path,
        width: int,
        height: int,
        fps: int,
        transition: str,
    ) -> float:
        meta = self._probe(source)
        start = max(0.0, min(float(start), meta["duration"] - 0.05))
        end = min(meta["duration"], max(start + 0.05, float(end)))
        seg_d = end - start
        fade_d = 0.18

        cmd = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", source]
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p"
        )
        if transition == "fade" and seg_d > 0.5:
            out_start = max(0.0, seg_d - fade_d)
            vf += f",fade=t=in:st=0:d={fade_d},fade=t=out:st={out_start:.3f}:d={fade_d}"

        cmd += ["-vf", vf]
        if meta["has_audio"]:
            af = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
            if transition == "fade" and seg_d > 0.5:
                out_start = max(0.0, seg_d - fade_d)
                af += f",afade=t=in:st=0:d={fade_d},afade=t=out:st={out_start:.3f}:d={fade_d}"
            cmd += ["-af", af, "-c:a", "aac", "-b:a", "160k"]
        else:
            cmd += [
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-map", "0:v:0", "-map", "1:a:0",
                "-shortest", "-c:a", "aac", "-b:a", "160k",
            ]

        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError((p.stderr or "FFmpeg segment normalize failed")[-2500:])
        return seg_d

    def render(
        self,
        clip_paths: list[str],
        trim_specs: list[dict] | None,
        aspect: str,
        quality: str,
        transition: str,
        output_filename: str,
        fps: int = 24,
        target_seconds: float | None = None,
        music_path: str | None = None,
        original_audio_volume: float = 0.18,
        title_text: str = "",
        ending_text: str = "",
        reuse_mode: str = "cycle",
    ) -> dict:
        if not clip_paths:
            raise RuntimeError("至少需要一支影片")
        if len(clip_paths) > 30:
            raise RuntimeError("v0.2 一次最多 30 支影片")
        if aspect not in {"9:16", "16:9"}:
            raise RuntimeError("只支援 9:16 或 16:9")
        if quality not in {"720p", "1080p"}:
            raise RuntimeError("只支援 720p 或 1080p")
        if transition not in {"cut", "fade"}:
            raise RuntimeError("transition 只支援 cut 或 fade")
        if reuse_mode not in {"cycle"}:
            raise RuntimeError("目前 reuse_mode 只支援 cycle")
        if not 0 <= float(original_audio_volume) <= 1:
            raise RuntimeError("original_audio_volume 必須介於 0 與 1")

        width, height = self._size(aspect, quality)
        trims = trim_specs or [{} for _ in clip_paths]
        if len(trims) != len(clip_paths):
            raise RuntimeError("trim_specs 數量必須和影片數量相同")

        probes = [self._probe(p) for p in clip_paths]
        specs: list[tuple[str, float, float]] = []
        for path, meta, spec in zip(clip_paths, probes, trims):
            start = max(0.0, float(spec.get("start", 0) or 0))
            requested_end = spec.get("end")
            end = float(requested_end) if requested_end not in (None, "", 0) else meta["duration"]
            end = min(meta["duration"], max(start + 0.05, end))
            specs.append((path, start, end))

        base_duration = sum(end - start for _, start, end in specs)
        desired = float(target_seconds) if target_seconds and float(target_seconds) > 0 else base_duration
        if desired > 900:
            raise RuntimeError("v0.2 單次輸出最長 900 秒")

        workdir = Path(tempfile.mkdtemp(prefix="catpaw_editor_", dir=str(self.output_dir)))
        try:
            normalized: list[tuple[Path, float]] = []
            for i, (path, start, end) in enumerate(specs):
                seg_path = workdir / f"seg_{i:03d}.mp4"
                dur = self._normalize_segment(
                    path, start, end, seg_path, width, height, fps, transition
                )
                normalized.append((seg_path, dur))

            concat_file = workdir / "concat.txt"
            lines: list[str] = []
            assembled = 0.0
            idx = 0
            # Reuse clips in cycle order until target duration is covered.
            while assembled < desired - 0.02:
                seg_path, seg_d = normalized[idx % len(normalized)]
                remain = desired - assembled
                if seg_d <= remain + 0.02:
                    lines.append(f"file '{seg_path.as_posix()}'")
                    assembled += seg_d
                else:
                    # Make exact final partial segment.
                    tail = workdir / f"tail_{idx:03d}.mp4"
                    cmd = [
                        "ffmpeg", "-y", "-i", str(seg_path), "-t", f"{remain:.3f}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", str(tail),
                    ]
                    p = subprocess.run(cmd, capture_output=True, text=True)
                    if p.returncode != 0:
                        raise RuntimeError((p.stderr or "FFmpeg tail failed")[-1800:])
                    lines.append(f"file '{tail.as_posix()}'")
                    assembled += remain
                idx += 1
                if idx > 1000:
                    raise RuntimeError("素材循環次數異常")

            concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            base_video = workdir / "base.mp4"
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-t", f"{desired:.3f}", "-c", "copy", str(base_video),
            ]
            p = subprocess.run(cmd, capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError((p.stderr or "FFmpeg concat failed")[-2200:])

            out = self.output_dir / output_filename
            font = self._fontfile()
            filters: list[str] = []
            vlabel = "[0:v]"

            draw_filters: list[str] = []
            if font and title_text:
                t = self._escape_drawtext(title_text)
                draw_filters.append(
                    f"drawtext=fontfile='{font}':text='{t}':fontcolor=white:"
                    f"fontsize={max(34, width//18)}:x=(w-text_w)/2:y=h*0.10:"
                    f"box=1:boxcolor=black@0.30:boxborderw=18:enable='between(t,0,2.2)'"
                )
            if font and ending_text:
                e = self._escape_drawtext(ending_text)
                start_end = max(0.0, desired - 2.2)
                draw_filters.append(
                    f"drawtext=fontfile='{font}':text='{e}':fontcolor=white:"
                    f"fontsize={max(34, width//18)}:x=(w-text_w)/2:y=h*0.82:"
                    f"box=1:boxcolor=black@0.34:boxborderw=18:enable='gte(t,{start_end:.3f})'"
                )

            cmd = ["ffmpeg", "-y", "-i", str(base_video)]
            if music_path:
                cmd += ["-stream_loop", "-1", "-i", music_path]

            if draw_filters:
                filters.append(vlabel + "," + ",".join(draw_filters) + "[vout]")
                video_map = "[vout]"
            else:
                video_map = "0:v:0"

            if music_path:
                # Base clip audio becomes low-level SFX bed under the song.
                filters.append(
                    f"[0:a]volume={float(original_audio_volume):.3f}[sfx];"
                    f"[1:a]aresample=48000,aformat=channel_layouts=stereo,"
                    f"volume=1.0[music];[music][sfx]amix=inputs=2:duration=first:"
                    f"dropout_transition=0,atrim=duration={desired:.3f}[aout]"
                )
                audio_map = "[aout]"
            else:
                audio_map = "0:a:0"

            if filters:
                cmd += ["-filter_complex", ";".join(filters)]

            cmd += [
                "-map", video_map, "-map", audio_map,
                "-t", f"{desired:.3f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "19",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(out),
            ]
            p = subprocess.run(cmd, capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError((p.stderr or "FFmpeg final render failed")[-3000:])

            return {
                "path": str(out),
                "width": width,
                "height": height,
                "fps": fps,
                "duration": round(desired, 3),
                "clip_count": len(clip_paths),
                "source_duration": round(base_duration, 3),
                "transition": transition,
                "quality": quality,
                "aspect": aspect,
                "music_attached": bool(music_path),
                "original_audio_volume": float(original_audio_volume),
                "reuse_mode": reuse_mode,
                "reuse_passes": idx,
                "title_text": title_text,
                "ending_text": ending_text,
            }
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
