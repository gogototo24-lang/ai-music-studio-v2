# 《貓掌江湖》／《喵台灣》AI 內容串聯流程

更新日期：2026-10-06

## 核心架構

```text
題材／角色設定
→ video-prompt-builder
→ 首幀／角色圖
→ 影片生成
→ AI Music Studio v2 音訊與合成
→ threads-scheduler 審核
→ 排程發布
```

## Step A：建立 Brief

每次先固定：

```json
{
  "universe": "貓掌江湖 | 喵台灣",
  "title": "",
  "character": "",
  "aspect_ratio": "9:16",
  "duration_seconds": 15,
  "goal": "",
  "continuity": [],
  "avoid": []
}
```

《貓掌江湖》固定：全母喵、9:16、電影級布袋戲武俠、非血腥、角色服裝與道具連續。

《喵台灣》固定：直式社群內容、題材先核實、公共事務採中立事實表述。

## Step B：video-prompt-builder

輸出四份資料：
1. `image_prompt`：角色／首幀
2. `video_prompt`：動作、運鏡、節奏
3. `audio_plan`：口白、BGM、環境音
4. `continuity_lock`：臉型、服裝、色彩、道具、場景不可變項

每一鏡盡量只保留一個主要動作與一個主要運鏡，降低角色漂移。

## Step C：首幀與角色圖

優先使用已確認的角色基準圖。新角色先完成：
- 全身乾淨基圖
- 正面角色識別
- 主色／服裝／配件鎖定
- 9:16 首幀

角色圖確認後才進影片生成。

## Step D：影片 Provider

### 現有
`threads-scheduler/src/ai-engine.js` 已支援：
- mock
- PixVerse

### 建議新增
Higgsfield Seedance 2.5 作第二影片 provider。

建議架構：

```text
threads-scheduler
  ↓ create job
Higgsfield adapter / backend
  ↓ request id
threads-scheduler
  ↓ poll status
R2 保存完成影片
```

避免把長時間輪詢直接塞在單次 Cloudflare Worker request。

## Step E：AI Music Studio v2

影片完成後使用：
- `/api/voice/generate`
- `/api/music/generate`
- `/api/mix`
- `/api/mv/render`
- `/api/mv/status/{job_id}`

《貓掌江湖》：短口白、招式音效、環境聲、BGM 不蓋人聲。

《喵台灣》：社群短句、簡潔 BGM、字幕清楚。

## Step F：threads-scheduler

目標資料流：

```text
scan
→ trend
→ content_draft
→ image job
→ video job
→ audio/MV job
→ review
→ approve
→ posts
→ scheduled publish
```

目前正式發布端只完整處理 TEXT / IMAGE。影片 job 已存在，但 VIDEO 發布尚未接到正式 Threads publisher。

## Secret

禁止進 Git：
- OPENAI_API_KEY
- PIXVERSE_API_KEY
- Higgsfield API credentials
- THREADS_APP_SECRET
- Threads access token
- ADMIN_KEY

Cloudflare 用 Worker Secrets；Render 用 Environment Variables。

## 三階段導入

### Phase 1：立即可用
Prompt Builder → 首幀 → PixVerse/Higgsfield 手動生成 → AI Music Studio v2 → 人工審核 → 排程。

### Phase 2：半自動
新增 Higgsfield adapter，讓 threads-scheduler 能建立與查詢 Seedance 任務。

### Phase 3：全自動
題材 → 草稿 → 圖 → 影片 → 音訊 → MV → 審核 → 排程。

保留人工審核閘門，避免錯圖、角色漂移或錯誤時事直接發布。
