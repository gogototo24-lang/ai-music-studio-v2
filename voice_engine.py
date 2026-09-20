# -*- coding: utf-8 -*-
"""
Character voiceover engine.
Uses Edge TTS for spoken voiceover, not singing synthesis.
"""
from __future__ import annotations
import asyncio
import shutil
import subprocess
from pathlib import Path

CHARACTER_PRESETS = {
    "heroine": {"name": "冷豔女俠", "voice": "zh-TW-HsiaoChenNeural", "pitch": "-2Hz", "rate": "-4%"},
    "overlord": {"name": "霸氣女王", "voice": "zh-TW-HsiaoChenNeural", "pitch": "-5Hz", "rate": "-8%"},
    "gentle": {"name": "溫柔女聲", "voice": "zh-TW-HsiaoYuNeural", "pitch": "+0Hz", "rate": "-5%"},
    "narrator": {"name": "電影旁白女聲", "voice": "zh-TW-HsiaoChenNeural", "pitch": "-3Hz", "rate": "-10%"},
}

class VoiceEngine:
    def __init__(self, output_dir="outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _require_ffmpeg(self):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("找不到 FFmpeg，請先安裝 FFmpeg。")

    def apply_hall_reverb(self, input_audio: str, output_audio: str):
        self._require_ffmpeg()
        cmd = [
            "ffmpeg", "-y", "-i", input_audio,
            "-af", "aecho=0.8:0.88:60|120:0.28|0.18,highpass=f=90,volume=1.1",
            output_audio,
        ]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            shutil.copy(input_audio, output_audio)
        return output_audio

    async def generate_voice(
        self,
        text: str,
        preset_key="heroine",
        enable_reverb=True,
        filename="voice.mp3",
    ):
        preset = CHARACTER_PRESETS.get(preset_key, CHARACTER_PRESETS["heroine"])
        raw_output = self.output_dir / f"raw_{filename}"
        final_output = self.output_dir / filename

        cmd = [
            "edge-tts",
            "--voice", preset["voice"],
            "--text", text,
            f"--pitch={preset['pitch']}",
            f"--rate={preset['rate']}",
            "--write-media", str(raw_output),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    stderr.decode("utf-8", "ignore")[:300] or "Edge TTS 失敗"
                )
        except FileNotFoundError:
            raise RuntimeError("找不到 edge-tts。請先執行 pip install edge-tts")

        if enable_reverb:
            self.apply_hall_reverb(str(raw_output), str(final_output))
            raw_output.unlink(missing_ok=True)
        else:
            shutil.move(str(raw_output), str(final_output))

        return str(final_output)
