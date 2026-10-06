# AI Music Studio v2

目前後端版本：**2.0.1**

這個 repository 是《貓掌江湖》與《喵台灣》影音工作流的後端層，負責原創歌詞、角色口白、背景音樂、混音、音訊處理，以及 9:16 / 16:9 MV 合成。

## 現有能力
- `GET /health`：執行環境與模型狀態
- `POST /api/lyrics/generate`：原創歌詞
- `POST /api/voice/generate`：角色口白
- `POST /api/music/generate`：BGM
- `POST /api/extract`：音訊分離
- `POST /api/mix`：口白＋BGM 混音
- `POST /api/mv/render`：9:16 / 16:9 MV 合成
- `GET /api/mv/status/{job_id}`：MV 任務狀態

## 建議總架構

```text
題材／劇情 brief
  ↓
video-prompt-builder
  ↓
首幀／角色圖
  ↓
影片模型（PixVerse 或 Higgsfield Seedance 2.5）
  ↓
AI Music Studio v2：口白／BGM／混音／FFmpeg 合成
  ↓
threads-scheduler：審核／排程／發布
```

完整步驟：
- `docs/MAOZHANG_MIAOTAIWAN_PIPELINE.md`
- `docs/UPGRADE_AUDIT_2026-10-06.md`

## GitHub Pages + Render

若前端與 API 分開部署，在前端載入腳本前設定：

```html
<script>
  window.__API_BASE__ = "https://your-render-app.onrender.com";
</script>
```

前端將呼叫 `${API_BASE}/health` 與 `${API_BASE}/api/...`。若未設定，則使用 same-origin。

## Secret 原則

以下憑證不得提交到 Git：
- OpenAI
- PixVerse
- Higgsfield
- Threads / Meta
- Cloudflare

只放 Render Environment Variables、Cloudflare Secrets 或其他伺服器端 Secret Store。
