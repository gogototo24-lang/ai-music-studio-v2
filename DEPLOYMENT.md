# AI Music Studio v2 - 部署指南

本文件說明如何在不同環境中部署本專案。

## 快速開始

### 本機開發（Lite 模式）

```bash
# 1. 安裝 FFmpeg
# macOS
brew install ffmpeg
# Ubuntu/Debian
sudo apt-get install ffmpeg
# Windows: https://ffmpeg.org/download.html

# 2. 安裝 Python 套件
pip install -r requirements.txt

# 3. 啟動後端
python app.py

# 4. 開啟瀏覽器
# http://localhost:8000
```

### 本機開發（AI 模式，需要 MusicGen）

```bash
# 額外安裝 AI 套件（需要網路連線，首次下載約 3-5GB）
pip install -r requirements-ai.txt

# 設定 GPU（若有 NVIDIA GPU）
export MUSICGEN_DEVICE=cuda
# 或 CPU 模式
export MUSICGEN_DEVICE=cpu

# 啟動後端
python app.py
```

## Docker 部署

### Lite 模式（推薦 Render 免費方案）

```bash
# 本機測試
docker build -t ai-music-studio-lite --target lite .
docker run -p 8000:8000 ai-music-studio-lite

# 檢查
curl http://localhost:8000/health
```

### AI 模式（推薦 GPU 雲端主機）

```bash
# 本機測試
docker build -t ai-music-studio-ai --target ai .
docker run -p 8000:8000 ai-music-studio-ai
```

### 使用 Docker Compose

```bash
# 同時啟動 Lite 和 AI 版本
docker-compose up

# 只啟動 Lite
docker-compose up ai-music-studio-lite

# 只啟動 AI
docker-compose up ai-music-studio-ai
```

後端地址：
- Lite：http://localhost:8000
- AI：http://localhost:8001

## 雲端部署

### 方案 1: Render（推薦，免費）

**適合：** Lite 模式（FFmpeg + Edge TTS）

步驟：

1. 登入 https://render.com/
2. 選擇 **New Web Service**
3. 連接 GitHub Repository：`gogototo24-lang/ai-music-studio-v2`
4. Render 會自動讀取 `Dockerfile` 和 `render.yaml`
5. 部署完成，獲得公開網址

功能：
- ✅ 原創歌詞生成
- ✅ Edge TTS 角色口白
- ✅ FFmpeg 測試配樂
- ✅ 音軌分離（使用 FFmpeg）
- ✅ Ducking 混音
- ✅ MV 渲染
- ❌ MusicGen AI 配樂（不支援免費方案）

---

### 方案 2: RunPod（推薦，支援 GPU）

**適合：** AI 模式（MusicGen + Demucs）

步驟：

1. 登入 https://www.runpod.io/
2. 選擇 **Pods** → **GPU Pods**
3. 選擇合適的 GPU（推薦 RTX 4090 或 A40）
4. 選擇 PyTorch 預設映像或使用自訂 Docker
5. 上傳本專案或連接 GitHub
6. 運行 `docker-compose up ai-music-studio-ai`
7. 設定 SSH/HTTP 端口映射

優點：
- MusicGen 會非常快（GPU 加速）
- 支援自訂環境
- 按小時計費

---

### 方案 3: Hugging Face Spaces

**適合：** AI 模式（小型演示）

步驟：

1. 登入 https://huggingface.co/spaces
2. 建立新 Space，選擇 **Docker**
3. 連接本 GitHub Repository
4. 設定環境變數
5. Spaces 會自動部署

限制：
- 免費方案有資源限制
- CPU 模式會比較慢
- 閒置 2 小時後會暫停

---

### 方案 4: Google Cloud Run

**適合：** Lite 或 AI 模式

步驟：

```bash
# 1. 安裝 Google Cloud CLI
# https://cloud.google.com/sdk/docs/install

# 2. 認證
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 3. 部署
gcloud run deploy ai-music-studio-v2 \
  --source . \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --timeout 3600 \
  --allow-unauthenticated

# 4. 取得公開網址
gcloud run services describe ai-music-studio-v2 --platform managed --region us-central1
```

---

### 方案 5: Railway

**適合：** Lite 模式

步驟：

1. 登入 https://railway.app/
2. 選擇 **New Project** → **Deploy from GitHub**
3. 連接 Repository
4. Railway 會自動部署
5. 設定環境變數（如需要）

---

## 環境變數設定

### Render 環境變數

在 Render Dashboard 的 **Environment** 中新增：

```
PORT=8000
MAX_UPLOAD_MB=120
CORS_ORIGINS=https://gogototo24-lang.github.io
```

若需要 MusicGen（Render GPU 方案）：

```
MUSICGEN_MODEL=facebook/musicgen-small
MUSICGEN_DEVICE=cuda
```

### 本機環境變數

建立 `.env` 檔案：

```bash
cp .env.example .env
# 編輯 .env
```

或直接匯出：

```bash
export MUSICGEN_DEVICE=cuda
export PORT=8000
python app.py
```

---

## 健康檢查

所有部署方案都支援以下健康檢查：

```bash
curl https://你的網址/health
```

回應範例：

```json
{
  "ok": true,
  "service": "ai-music-studio-v2",
  "version": "2.0.1",
  "ffmpeg": true,
  "musicgen": false,
  "cuda_available": false,
  "device": "cpu",
  "model_name": "facebook/musicgen-small",
  "fallback_enabled": true,
  "demucs": false
}
```

---

## 前端連線

### 同源部署（推薦）

```text
https://你的網址/
```

前端會自動找到後端（都在同一個域名）。

### 跨域部署（需要 CORS）

如果前端在 GitHub Pages：

```text
https://gogototo24-lang.github.io/ai-music-studio-v2/
```

後端需要允許 CORS。目前已預設允許：

```text
https://gogototo24-lang.github.io
```

若需要新增其他前端網址，修改環境變數：

```
CORS_ORIGINS=https://gogototo24-lang.github.io,https://你的前端網址
```

---

## 常見問題

### Q1: MusicGen 下載很慢？

A: 首次執行會從 Hugging Face 下載 3-5GB 模型。建議：
- 使用有線網路
- 預先下載模型：
  ```python
  from audiocraft.models import MusicGen
  MusicGen.get_pretrained("facebook/musicgen-small")
  ```

### Q2: 記憶體不足？

A: MusicGen 需要 8GB+ RAM。若記憶體不足：
- 使用 CPU 模式會自動轉用非 GPU 回退
- 考慮使用 GPU 雲端主機
- 或停留在 Lite 模式

### Q3: Render 上 MusicGen 不可用？

A: 正常的。Render 免費方案沒有 GPU。要用 MusicGen 請改用：
- RunPod
- Google Cloud GPU
- AWS EC2 GPU
- 自有 GPU 伺服器

### Q4: 如何在本機測試 Render 部署？

A: 使用 Docker：
```bash
docker build -t ai-music-studio-lite --target lite .
docker run -p 8000:8000 ai-music-studio-lite
curl http://localhost:8000/health
```

### Q5: 前端無法連接後端？

A: 檢查：
1. CORS 是否正確設定
2. 後端是否真的在線
3. 前端網址是否在允許清單中
4. 檢查瀏覽器 Console 的錯誤訊息

---

## 推薦部署組合

### 快速演示（免費）

```text
前端：GitHub Pages
後端：Render Lite 模式
```

### 小規模生產

```text
前端：GitHub Pages / Vercel
後端：Render Lite + 本機 MusicGen（自有伺服器）
```

### 完整 AI 工作室

```text
前端：自訂域名 / Vercel
後端：RunPod GPU + Render Lite 備份
```

---

## 技術支援

有問題？檢查：
1. `/health` 端點狀態
2. Docker 容器日誌
3. 環境變數是否正確設定
4. 網路連線與防火牆
5. GitHub Issues
