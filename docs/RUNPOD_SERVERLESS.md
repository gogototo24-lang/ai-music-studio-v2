# RunPod Serverless｜CatPaw YuE2

這是 C「音樂 MV」產線的 GPU 執行層。Render 保留控制 API；RunPod 只在真正生成歌曲時使用 GPU。

## 已準備的檔案

- `deploy/runpod/Dockerfile`
- `providers/runpod_yue2_handler.py`
- `requirements-runpod-yue2.txt`
- `examples/runpod-wumei-test.json`

## RunPod Endpoint 建議

第一階段只做單筆驗收：

- Queue-based Serverless
- GPU：24GB class（L4 / A5000 / 3090 / MIG 24GB）
- Flex workers
- Max workers: 1
- Active workers: 0
- Idle timeout：使用平台預設或最短合理值
- Network volume：建議掛載，用來快取 Hugging Face 模型，減少冷啟動重下載

## Render 主 API 需要的 Secret

```text
RUNPOD_API_KEY=<RunPod API Key>
RUNPOD_ENDPOINT_ID=<Serverless Endpoint ID>
MUSIC_PRIMARY_PROVIDER=runpod-yue2
RUNPOD_TIMEOUT_SECONDS=900
RUNPOD_POLL_SECONDS=4
```

API Key 不可提交 Git。

## 執行模式

主 API 使用非同步：

```text
POST https://api.runpod.ai/v2/{endpoint}/run
GET  https://api.runpod.ai/v2/{endpoint}/status/{job_id}
```

不自動重送逾時任務，避免重複 GPU 計費。

## 音訊回傳

Worker 使用 FLAC + base64 JSON 回傳，主 API 解碼後存進 Render outputs，供現有前端播放器與 C 產線使用。

## 成本閘門

目前程式準備完成 ≠ 已開啟付費 GPU。

真正建立 RunPod Endpoint 前先確認：
1. 帳號已有可用額度／付款方式。
2. GPU 價格。
3. Max workers = 1。
4. 先跑 `examples/runpod-wumei-test.json` 一筆。
5. 成功後再切 `MUSIC_PRIMARY_PROVIDER=runpod-yue2`。
