# -*- coding: utf-8 -*-
"""
Character voiceover engine for AI Music Studio v2.

Uses Edge TTS for spoken Taiwanese Mandarin voiceover. Presets tune pitch/rate
for character direction; they are not singing synthesis and are not a native
Taiwanese-Hokkien voice model.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path


CHARACTER_PRESETS = {
    "heroine": {
        "name": "冷豔女俠",
        "voice": "zh-TW-HsiaoChenNeural",
        "pitch": "-2Hz",
        "rate": "-4%",
        "description": "冷靜、俐落、帶距離感，適合月扇影喵一類角色。",
        "recommended_for": ["月扇影喵", "血紋劍喵"],
    },
    "overlord": {
        "name": "霸氣女王",
        "voice": "zh-TW-HsiaoChenNeural",
        "pitch": "-5Hz",
        "rate": "-8%",
        "description": "低沉、穩重、壓迫感較強，適合高位者或強勢角色。",
        "recommended_for": ["白狂天喵", "焚天赤焰喵"],
    },
    "empress": {
        "name": "皇者威儀",
        "voice": "zh-TW-HsiaoChenNeural",
        "pitch": "-7Hz",
        "rate": "-12%",
        "description": "速度較慢、氣場厚重，適合峰主、帝尊、宗主式角色。",
        "recommended_for": ["白帝喵尊"],
    },
    "narrator": {
        "name": "電影旁白",
        "voice": "zh-TW-HsiaoChenNeural",
        "pitch": "-3Hz",
        "rate": "-10%",
        "description": "敘事清楚、節奏沉穩，適合片頭詩號與世界觀旁白。",
        "recommended_for": ["旁白", "片頭詩號", "預告"],
    },
    "gentle": {
        "name": "溫柔女聲",
        "voice": "zh-TW-HsiaoYuNeural",
        "pitch": "+0Hz",
        "rate": "-5%",
        "description": "柔和自然，適合情感、文戲與溫暖社群短片。",
        "recommended_for": ["琉璃喵", "喵台灣"],
    },
    "ethereal": {
        "name": "空靈女聲",
        "voice": "zh-TW-HsiaoYuNeural",
        "pitch": "+3Hz",
        "rate": "-8%",
        "description": "清透、慢速、夢幻，適合時間、月光或靈性角色。",
        "recommended_for": ["歲璃喵", "星織霜雨"],
    },
    "youth": {
        "name": "青春女聲",
        "voice": "zh-TW-HsiaoYuNeural",
        "pitch": "+5Hz",
        "rate": "+3%",
        "description": "明亮、速度稍快，適合輕快社群短片與年輕角色。",
        "recommended_for": ["喵台灣", "輕快角色"],
    },
    "battle": {
        "name": "武戲喝聲",
        "voice": "zh-TW-HsiaoChenNeural",
        "pitch": "-4Hz",
        "rate": "+4%",
        "description": "短句俐落、節奏更快，適合 2–6 秒武戲口白。",
        "recommended_for": ["貓掌江湖武戲", "招式名"],
    },
}


def public_voice_presets():
    return [
        {
            "key": key,
            "name": preset["name"],
            "voice": preset["voice"],
            "pitch": preset["pitch"],
            "rate": preset["rate"],
            "description": preset["description"],
            "recommended_for": preset["recommended_for"],
        }
        for key, preset in CHARACTER_PRESETS.items()
    ]


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
        preset = CHARACTER_PRESETS.get(preset_key)
        if preset is None:
            raise ValueError(f"未知聲線 preset：{preset_key}")

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
