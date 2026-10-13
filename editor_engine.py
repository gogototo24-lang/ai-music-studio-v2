# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable


class EditorEngine:
    """FFmpeg-only editor for CatPaw generated clips."""

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
            raise RuntimeError(f"讀不到影片長度：{Path(path).name}")
        return {"duration": duration, "has_audio": has_audio}

    @staticmethod
    def _size(aspect: str, quality: str) -> tuple[int, int]:
        if aspect == "16:9":
            return (1920, 1080) if quality == "1080p" else (1280, 720)
        return (1080, 1920) if quality == "1080p" else (720, 1280)

    def render(
        self,
        clip_paths: list[str],
        trim_specs: list[dict] | None,
        aspect: str,
        quality: str,
        transition: str,
        output_filename: str,
        fps: int = 24,
    ) -> dict:
        if not clip_paths:
            raise RuntimeError("至少需要一支影片")
        if len(clip_paths) > 20:
            raise RuntimeError("v0.1 一次最多 20 支影片")
        if aspect not in {"9:16", "16:9"}:
            raise RuntimeError("只支援 9:16 或 16:9")
        if quality not in {"720p", "1080p"}:
            raise RuntimeError("只支援 720p 或 1080p")
        if transition not in {"cut", "fade"}:
            raise RuntimeError("transition 只支援 cut 或 fade")

        width, height = self._size(aspect, quality)
        trims = trim_specs or [{} for _ in clip_paths]
        if len(trims) != len(clip_paths):
            raise RuntimeError("trim_specs 數量必須和影片數量相同")

        probes = [self._probe(p) for p in clip_paths]
        cmd = ["ffmpeg", "-y"]
        for p in clip_paths:
            cmd += ["-i", str(p)]

        filters: list[str] = []
        concat_inputs: list[str] = []
        total_duration = 0.0
        fade_d = 0.18

        for i, (path, meta, spec) in enumerate(zip(clip_paths, probes, trims)):
            start = max(0.0, float(spec.get("start", 0) or 0))
            requested_end = spec.get("end")
            end = float(requested_end) if requested_end not in (None, "", 0) else meta["duration"]
            end = min(meta["duration"], max(start + 0.05, end))
            seg_d = end - start
            total_duration += seg_d

            vf = (
                f"[{i}:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p"
            )
            if transition == "fade" and seg_d > 0.5:
                out_start = max(0.0, seg_d - fade_d)
                vf += f",fade=t=in:st=0:d={fade_d},fade=t=out:st={out_start:.3f}:d={fade_d}"
            vf += f"[v{i}]"
            filters.append(vf)

            if meta["has_audio"]:
                af = (
                    f"[{i}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,"
                    f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
                )
                if transition == "fade" and seg_d > 0.5:
                    out_start = max(0.0, seg_d - fade_d)
                    af += f",afade=t=in:st=0:d={fade_d},afade=t=out:st={out_start:.3f}:d={fade_d}"
                af += f"[a{i}]"
            else:
                af = (
                    f"anullsrc=r=48000:cl=stereo,atrim=duration={seg_d:.3f},"
                    f"asetpts=PTS-STARTPTS[a{i}]"
                )
            filters.append(af)
            concat_inputs.append(f"[v{i}][a{i}]")

        filters.append("".join(concat_inputs) + f"concat=n={len(clip_paths)}:v=1:a=1[vout][aout]")
        out = self.output_dir / output_filename
        cmd += [
            "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "19",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError((p.stderr or "FFmpeg render failed")[-2500:])

        return {
            "path": str(out),
            "width": width,
            "height": height,
            "fps": fps,
            "duration": round(total_duration, 3),
            "clip_count": len(clip_paths),
            "transition": transition,
            "quality": quality,
            "aspect": aspect,
        }
