# -*- coding: utf-8 -*-
"""
RunningHub voice workflow adapter.

Uses a hosted RunningHub ComfyUI workflow as a GPU voice provider.
The workflow is expected to contain a text input node and a SaveAudio/SaveAudioMP3 output.
Reference voice/audio can remain embedded in the workflow itself.

Environment:
RUNNINGHUB_API_KEY
RUNNINGHUB_VOICE_WORKFLOW_ID
RUNNINGHUB_TEXT_NODE_ID
RUNNINGHUB_TEXT_FIELD=prompt\nRUNNINGHUB_SPEAKER_NODE_ID=11\nRUNNINGHUB_SPEAKER_FIELD=prompt
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
        text_node_id = os.getenv("RUNNINGHUB_TEXT_NODE_ID", "").strip()
        text_field = os.getenv("RUNNINGHUB_TEXT_FIELD", "prompt").strip() or "prompt"\n        speaker_node_id = os.getenv("RUNNINGHUB_SPEAKER_NODE_ID", "").strip()\n        speaker_field = os.getenv("RUNNINGHUB_SPEAKER_FIELD", "prompt").strip() or "prompt"
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
            "text_field": text_field,\n            "speaker_node_id": speaker_node_id,\n            "speaker_field": speaker_field,
            "base_url": base_url,
            "poll_seconds": poll_seconds,
            "max_wait": max_wait,
        }

    async def generate(
        self,
        *,
        text: str,
        filename_stem: str,
    ) -> str:
        cfg = self._config()
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
            "Host": "www.runninghub.ai",
        }
        payload = {
            "apiKey": cfg["api_key"],
            "workflowId": cfg["workflow_id"],
            "nodeInfoList": [
                {
                    "nodeId": cfg["text_node_id"],
                    "fieldName": cfg["text_field"],
                    "fieldValue": text,
                }
            ],
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
                        if file_url.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")):
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
