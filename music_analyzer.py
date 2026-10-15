# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path


class MusicAnalyzer:
    """Lightweight FFmpeg + stdlib music analysis for CatPaw Editor v0.3."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _run(self, cmd: list[str], label: str):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError((p.stderr or f"{label} failed")[-2500:])
        return p

    def extract_audio(self, source_path: str, output_filename: str, bitrate: str = "320k") -> dict:
        out = self.output_dir / output_filename
        self._run(
            [
                "ffmpeg", "-y", "-i", str(source_path), "-vn",
                "-c:a", "libmp3lame", "-b:a", bitrate,
                "-ar", "44100", "-ac", "2",
                "-movflags", "+faststart", str(out)
            ],
            "音訊擷取",
        )
        duration = self._duration(str(out))
        return {"path": str(out), "duration": duration, "bitrate": bitrate, "format": "mp3"}

    def _duration(self, path: str) -> float:
        p = self._run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
            "ffprobe",
        )
        try:
            return round(float((p.stdout or "0").strip()), 3)
        except Exception:
            return 0.0

    def _pcm_envelope(self, source_path: str, hop_seconds: float = 0.10) -> tuple[list[float], float]:
        with tempfile.TemporaryDirectory(prefix="catpaw_music_") as td:
            wav_path = Path(td) / "mono.wav"
            self._run(
                [
                    "ffmpeg", "-y", "-i", str(source_path), "-vn",
                    "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le",
                    str(wav_path)
                ],
                "分析音訊轉碼",
            )
            with wave.open(str(wav_path), "rb") as wf:
                rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
            if not frames:
                return [], 0.0
            count = len(frames) // 2
            samples = struct.unpack("<" + "h" * count, frames[:count * 2])
            hop = max(1, int(rate * hop_seconds))
            env: list[float] = []
            for i in range(0, len(samples), hop):
                block = samples[i:i + hop]
                if not block:
                    break
                sq = sum((x / 32768.0) ** 2 for x in block) / len(block)
                env.append(math.sqrt(max(0.0, sq)))
            return env, hop_seconds

    @staticmethod
    def _normalize(values: list[float]) -> list[float]:
        if not values:
            return []
        lo, hi = min(values), max(values)
        if hi - lo < 1e-9:
            return [0.0 for _ in values]
        return [(x - lo) / (hi - lo) for x in values]

    def _estimate_bpm(self, env: list[float], hop: float) -> float | None:
        if len(env) < 80:
            return None
        x = self._normalize(env)
        mean = sum(x) / len(x)
        centered = [v - mean for v in x]
        best = (0.0, None)
        for bpm in range(70, 181):
            lag = max(1, int(round((60.0 / bpm) / hop)))
            if lag >= len(centered) // 2:
                continue
            score = sum(centered[i] * centered[i - lag] for i in range(lag, len(centered)))
            score /= max(1, len(centered) - lag)
            if score > best[0]:
                best = (score, bpm)
        return float(best[1]) if best[1] else None

    def _high_energy_sections(self, env: list[float], hop: float, duration: float) -> list[dict]:
        if not env:
            return []
        norm = self._normalize(env)
        window_seconds = 12.0 if duration >= 90 else 6.0
        win = max(1, int(round(window_seconds / hop)))
        scores = []
        for i in range(0, max(1, len(norm) - win + 1)):
            seg = norm[i:i + win]
            if seg:
                scores.append((sum(seg) / len(seg), i))
        scores.sort(reverse=True)
        chosen: list[dict] = []
        for score, i in scores:
            start = i * hop
            end = min(duration, start + window_seconds)
            if any(abs(start - x["start"]) < window_seconds * 0.75 for x in chosen):
                continue
            chosen.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "energy_score": round(score, 3),
                "label": "chorus_candidate",
            })
            if len(chosen) >= 3:
                break
        return sorted(chosen, key=lambda x: x["start"])

    def analyze(self, source_path: str) -> dict:
        duration = self._duration(source_path)
        env, hop = self._pcm_envelope(source_path)
        bpm = self._estimate_bpm(env, hop)
        energy = self._normalize(env)
        avg = round(sum(energy) / len(energy), 3) if energy else 0.0
        peaks = sorted(
            [{"time": round(i * hop, 2), "energy": round(v, 3)} for i, v in enumerate(energy)],
            key=lambda x: x["energy"],
            reverse=True,
        )[:12]
        return {
            "duration": duration,
            "bpm_estimate": bpm,
            "analysis_hop_seconds": hop,
            "average_energy": avg,
            "chorus_candidates": self._high_energy_sections(env, hop, duration),
            "peak_candidates": sorted(peaks, key=lambda x: x["time"]),
            "note": "BPM 與副歌候選為輕量啟發式分析，適合自動剪輯卡點初判；正式音樂製作仍應允許人工覆核。"
        }
