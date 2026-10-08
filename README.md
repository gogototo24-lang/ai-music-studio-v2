# AI Music Studio v2

目前後端版本：**2.3.0**

這個 repository 是《貓掌江湖》與《喵台灣》影音工作流的後端層，負責原創歌詞、角色口白、背景音樂、混音、音訊處理，以及 9:16 / 16:9 MV 合成。

## v2.3 自家 Music API

- 不再要求 ElevenLabs 才能生成音樂
- `MusicProviderRouter`：auto / MusicGen / YuE2 / ACE-Step
- MusicGen：本地 BGM fallback
- YuE2：自架完整歌曲、指定歌詞、人聲主力
- ACE-Step：自架快速歌曲／音樂候選
- `GET /api/music/providers`：查看音樂 provider 狀態
- `POST /api/music/generate`：統一歌曲／BGM API
- 完整說明：`docs/SELF_HOSTED_MUSIC_API.md`

## v2.2 聲線 Provider

- 保留 Edge TTS 作為永遠可用的輕量 fallback
- 新增 CosyVoice 3 遠端 provider 介面
- 新增 PilotTTS 遠端 provider 介面，優先測試 `zh-minnan`
- 新增 GPT-SoVITS 官方 HTTP API 介面，適合固定角色聲紋
- `GET /api/voice/providers`：查看 provider 是否已配置
- `POST /api/voice/generate` 新增 `provider`、`language`、`emotion`、`reference_id`
- 大型模型與主 Render Lite 分離，避免 RAM / GPU 資源衝突
- 完整部署說明：`docs/VOICE_PROVIDERS.md`

## v2.1 新增

- 8 種角色聲線：冷豔女俠、霸氣女王、皇者威儀、電影旁白、溫柔女聲、空靈女聲、青春女聲、武戲喝聲
- `GET /api/voice/presets`：聲線清單與角色建議
- 多素材 MV：圖片／影片依選取順序串接，不再只取第一個素材
- 最多 12 個畫面素材
- 可選字幕燒錄；若 FFmpeg 字幕濾鏡不可用，會保留 SRT sidecar 並完成無燒錄版 MP4

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


## 自家完整歌曲服務安全設定

主 API 與 GPU Music service 必須設定相同的 `MUSIC_SERVICE_TOKEN`。
這個 Token 只放平台 Secret / Environment，不提交 Git。

第一首驗收 payload：
`examples/wumei-yue2-song.json`

GPU 部署入口：
`deploy/yue2/Dockerfile`
