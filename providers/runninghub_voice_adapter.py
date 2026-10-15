# -*- coding: utf-8 -*-
"""
RunningHub VoxCPM2 voice workflow adapter.

Expected workflow contract:
- node 10 / field prompt: script text
- node 11 / field prompt: speaker description
- node 7: SaveAudio output

Environment:
RUNNINGHUB_API_KEY
RUNNINGHUB_VOICE_WORKFLOW_ID
RUNNINGHUB_TEXT_NODE_ID=10
RUNNINGHUB_TEXT_FIELD=prompt
RUNNINGHUB_SPEAKER_NODE_ID=11
RUNNINGHUB_SPEAKER_FIELD=prompt
RUNNINGHUB_POLL_SECONDS=5
RUNNINGHUB_MAX_WAIT_SECONDS=180
RUNNINGHUB_BASE_URL=https://www.runninghub.ai
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx


class RunningHubVoiceAdapter:
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def configured(self) -> bool:
        return bool(
            os.getenv("RUNNINGHUB_API_KEY", "").strip()
            and os.getenv("RUNNINGHUB_VOICE_WORKFLOW_ID", "").strip()
            and os.getenv("RUNNINGHUB_TEXT_NODE_ID", "").strip()
        )

    def _config(self) -> dict[str, Any]:
        api_key = os.getenv("RUNNINGHUB_API_KEY", "").strip()
        workflow_id = os.getenv("RUNNINGHUB_VOICE_WORKFLOW_ID", "").strip()
        text_node_id = os.getenv("RUNNINGHUB_TEXT_NODE_ID", "10").strip() or "10"
        text_field = os.getenv("RUNNINGHUB_TEXT_FIELD", "prompt").strip() or "prompt"
        speaker_node_id = os.getenv("RUNNINGHUB_SPEAKER_NODE_ID", "11").strip() or "11"
        speaker_field = os.getenv("RUNNINGHUB_SPEAKER_FIELD", "prompt").strip() or "prompt"
        base_url = os.getenv("RUNNINGHUB_BASE_URL", "https://www.runninghub.ai").rstrip("/")
        poll_seconds = float(os.getenv("RUNNINGHUB_POLL_SECONDS", "5"))
        max_wait = float(os.getenv("RUNNINGHUB_MAX_WAIT_SECONDS", "180"))
        if not (api_key and workflow_id and text_node_id):
            raise RuntimeError(
                "RunningHub 尚未完成設定：需要 RUNNINGHUB_API_KEY、"
                "RUNNINGHUB_VOICE_WORKFLOW_ID、RUNNINGHUB_TEXT_NODE_ID"
            )
        return {
            "api_key": api_key,
            "workflow_id": workflow_id,
            "text_node_id": text_node_id,
            "text_field": text_field,
            "speaker_node_id": speaker_node_id,
            "speaker_field": speaker_field,
            "base_url": base_url,
            "poll_seconds": poll_seconds,
            "max_wait": max_wait,
        }

    def _speaker_prompt(self, preset: str, language: str, emotion: str) -> str:
        profiles = {
            "heroine": "25歲女性，聲線清亮有力量，語速中等，咬字清楚，帶電影級武俠女主角氣勢",
            "white-emperor": "成熟女性，聲線低沉威儀、冷靜克制，語速偏慢，句尾有壓迫感",
            "moonfan": "成熟女性，聲線清冷內斂，語速偏慢，情緒克制",
            "suili": "年輕女性，聲線空靈柔和，語速偏慢，帶神秘感",
            "liuli": "年輕女性，聲線溫柔明亮，語速自然，親和但不稚嫩",
            "liuxia": "成熟女性，聲線清冷略帶沙啞，語速偏慢，前段克制，句尾孤傲，高潮時提升力度但不尖銳，帶俠氣與宿命感",
        }
        desc = profiles.get(preset, profiles["heroine"])
        return f"[spk1]{desc}；語言={language}；情緒={emotion}"

    async def generate(
        self,
        *,
        text: str,
        filename_stem: str,
        preset: str = "heroine",
        language: str = "zh-TW",
        emotion: str = "neutral",
    ) -> str:
        cfg = self._config()
        headers = {
            "Content-Type": "application/json",
        }

        script_prompt = text if str(text).lstrip().startswith("[spk") else f"[spk1]{text}"
        node_info = [
            {
                "nodeId": cfg["text_node_id"],
                "fieldName": cfg["text_field"],
                "fieldValue": script_prompt,
            },
            {
                "nodeId": cfg["speaker_node_id"],
                "fieldName": cfg["speaker_field"],
                "fieldValue": self._speaker_prompt(preset, language, emotion),
            },
        ]

        payload = {
            "apiKey": cfg["api_key"],
            "workflowId": cfg["workflow_id"],
            "nodeInfoList": node_info,
            "addMetadata": True,
        }

        timeout = httpx.Timeout(cfg["max_wait"] + 30, connect=20)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            submit = await client.post(
                cfg["base_url"] + "/task/openapi/create",
                headers=headers,
                json=payload,
            )
            submit.raise_for_status()
            body = submit.json()
            if body.get("code") != 0:
                raise RuntimeError(
                    f"RunningHub 提交失敗：{body.get('code')} {body.get('msg')}"
                )

            data = body.get("data") or {}
            task_id = data.get("taskId")
            if not task_id:
                raise RuntimeError("RunningHub 未回傳 taskId")

            waited = 0.0
            while waited <= cfg["max_wait"]:
                result = await client.post(
                    cfg["base_url"] + "/task/openapi/outputs",
                    headers=headers,
                    json={"apiKey": cfg["api_key"], "taskId": task_id},
                )
                result.raise_for_status()
                result_body = result.json()
                outputs = result_body.get("data")

                if isinstance(outputs, list) and outputs:
                    audio = None
                    for item in outputs:
                        file_url = str(item.get("fileUrl") or "")
                        file_type = str(item.get("fileType") or "").lower()
                        if file_type in {"mp3", "wav", "m4a", "aac", "ogg", "flac"}:
                            audio = item
                            break
                        if file_url.lower().endswith(
                            (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
                        ):
                            audio = item
                            break

                    if audio is None:
                        raise RuntimeError(
                            "RunningHub 工作流已完成，但沒有找到音訊輸出；"
                            "請確認工作流最後使用 SaveAudio/SaveAudioMP3"
                        )

                    file_url = audio.get("fileUrl")
                    response = await client.get(file_url)
                    response.raise_for_status()
                    suffix = Path(str(file_url).split("?")[0]).suffix.lower() or ".wav"
                    target = self.output_dir / f"{filename_stem}{suffix}"
                    target.write_bytes(response.content)

                    if target.stat().st_size < 128:
                        target.unlink(missing_ok=True)
                        raise RuntimeError("RunningHub 回傳音訊檔過小或為空")

                    return str(target)

                await asyncio.sleep(cfg["poll_seconds"])
                waited += cfg["poll_seconds"]

        raise RuntimeError("RunningHub 聲線工作流逾時")
