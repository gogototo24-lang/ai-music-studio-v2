# AI Music Studio v2 - 完整設置指南

這是最詳細的一步步安裝指南。

---

## 階段 1: 系統準備

### Step 1.1: 安裝 Python 3.11

#### macOS

```bash
brew install python@3.11
python3.11 --version
```

#### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv python3.11-dev
python3.11 --version
```

#### Windows

1. 下載：https://www.python.org/downloads/
2. 選擇 Python 3.11
3. 安裝時勾選「Add Python to PATH」
4. 開啟 PowerShell，驗證：
   ```powershell
   python --version
   ```

### Step 1.2: 安裝 FFmpeg（必要）

#### macOS

```bash
brew install ffmpeg
ffmpeg -version
```

#### Ubuntu / Debian

```bash
sudo apt-get install ffmpeg
ffmpeg -version
```

#### Windows

1. 下載：https://ffmpeg.org/download.html
2. 或使用 Chocolatey：
   ```powershell
   choco install ffmpeg
   ```
3. 或使用 Windows Package Manager：
   ```powershell
   winget install ffmpeg
   ```
4. 驗證：
   ```powershell
   ffmpeg -version
   ```

### Step 1.3: 克隆本專案

```bash
git clone https://github.com/gogototo24-lang/ai-music-studio-v2.git
cd ai-music-studio-v2
```

### Step 1.4: 建立虛擬環境（推薦）

```bash
# macOS / Linux
python3.11 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

---

## 階段 2: 基礎安裝（Lite 模式）

此模式包含：
- 歌詞生成
- Edge TTS 角色口白
- FFmpeg 測試配樂
- 音軌混音
- MV 合成

### Step 2.1: 安裝基礎套件

```bash
pip install -r requirements.txt
```

### Step 2.2: 驗證安裝

```bash
python -c "import fastapi; import uvicorn; import edge_tts; print('✓ 基礎套件安裝成功')"
```

### Step 2.3: 啟動後端

```bash
python app.py
```

您應該看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2.4: 測試後端

開啟新的終端：

```bash
curl http://localhost:8000/health
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

### Step 2.5: 開啟網頁介面

瀏覽器開啟：

```text
http://localhost:8000
```

現在可以開始使用了！

---

## 階段 3: AI 模式安裝（可選，需要 MusicGen）

此模式額外包含：
- MusicGen AI 配樂
- Demucs 音軌分離

### 系統要求

- **磁碟空間**：至少 10GB（模型下載 3-5GB + 緩存）
- **記憶體**：8GB+ 推薦
- **網路**：首次下載需要穩定網路
- **GPU**（可選）：NVIDIA GPU 會快 10-50 倍

### Step 3.1: 安裝 PyTorch

#### CPU 版本（任何人都可以用，但較慢）

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

#### GPU 版本（NVIDIA CUDA 12.1）

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### 其他 CUDA 版本

訪問 https://pytorch.org/get-started/locally/ 選擇您的配置。

### Step 3.2: 驗證 PyTorch

```bash
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}')"
```

### Step 3.3: 安裝 AudioCraft 和 Demucs

```bash
pip install -r requirements-ai.txt
```

### Step 3.4: 預先下載 MusicGen 模型（可選但推薦）

```python
python << 'EOF'
from audiocraft.models import MusicGen
print("正在下載 MusicGen 模型...")
model = MusicGen.get_pretrained("facebook/musicgen-small")
print("✓ 模型下載完成")
EOF
```

這會下載約 3-5GB，只需做一次。

### Step 3.5: 設定 MusicGen 裝置

#### 使用 GPU（如果有 CUDA）

```bash
# macOS / Linux
export MUSICGEN_DEVICE=cuda

# Windows PowerShell
$env:MUSICGEN_DEVICE="cuda"
```

#### 使用 CPU（預設）

```bash
# macOS / Linux
export MUSICGEN_DEVICE=cpu

# Windows PowerShell
$env:MUSICGEN_DEVICE="cpu"
```

### Step 3.6: 啟動後端（AI 模式）

```bash
python app.py
```

### Step 3.7: 驗證 MusicGen

```bash
curl http://localhost:8000/health | python -m json.tool
```

應該看到 `"musicgen": true`

---

## 階段 4: Docker 部署（可選）

### Step 4.1: 安裝 Docker

https://docs.docker.com/get-docker/

### Step 4.2: 構建 Lite 版本

```bash
docker build -t ai-music-studio-lite --target lite .
```

### Step 4.3: 運行 Lite 版本

```bash
docker run -p 8000:8000 ai-music-studio-lite
```

### Step 4.4: 構建 AI 版本

```bash
docker build -t ai-music-studio-ai --target ai .
```

### Step 4.5: 運行 AI 版本

```bash
docker run -p 8000:8000 ai-music-studio-ai
```

### Step 4.6: 使用 Docker Compose（同時運行兩個版本）

```bash
docker-compose up
```

- Lite：http://localhost:8000
- AI：http://localhost:8001

---

## 階段 5: 雲端部署

### 方案 A: Render（免費，Lite 模式）

1. 登入 https://render.com/
2. 點選 **New Web Service**
3. 連接 GitHub
4. 選擇 `gogototo24-lang/ai-music-studio-v2`
5. Render 自動讀取 `Dockerfile` 並部署
6. 等待部署完成，獲得公開網址

公開網址會是：

```text
https://ai-music-studio-v2-xxxx.onrender.com/
```

### 方案 B: RunPod（支援 GPU，適合 AI 模式）

參考 `DEPLOYMENT.md` 中的 RunPod 章節。

### 方案 C: Google Cloud Run

參考 `DEPLOYMENT.md` 中的 Google Cloud Run 章節。

---

## 階段 6: 前端連線

### 本機使用（自動）

前端已經在 `http://localhost:8000`，自動連接後端。

### 遠端使用（Render）

對於公開網址 `https://ai-music-studio-v2-xxxx.onrender.com/`，前端同樣自動連接。

### 獨立前端（GitHub Pages）

如果把前端放在 GitHub Pages，需要修改前端代碼，將相對路徑改成絕對路徑：

```javascript
const API_BASE = "https://ai-music-studio-v2-xxxx.onrender.com";
```

---

## 測試清單

- [ ] `/health` 回傳 ok
- [ ] 首頁可以開啟
- [ ] 可以生成歌詞
- [ ] 可以生成角色口白
- [ ] 可以生成 BGM（FFmpeg 或 MusicGen）
- [ ] 可以分離音軌
- [ ] 可以混音
- [ ] 可以生成 MV

---

## 常見錯誤排查

### 錯誤：`ffmpeg not found`

**解決**：安裝 FFmpeg（見 Step 1.2）

### 錯誤：`ModuleNotFoundError: No module named 'fastapi'`

**解決**：
```bash
pip install -r requirements.txt
```

### 錯誤：`CUDA not available`

**解決**：
```bash
export MUSICGEN_DEVICE=cpu
```

### 錯誤：`model download failed`

**解決**：
- 檢查網路連線
- 預先下載模型（Step 3.4）
- 檢查磁碟空間

### 錯誤：`port 8000 already in use`

**解決**：
```bash
export PORT=8001
python app.py
```

或殺死佔用該埠的進程。

---

## 需要幫助？

- 檢查 GitHub Issues
- 查看 `DEPLOYMENT.md` 的常見問題
- 檢查 `/health` 端點狀態
- 查看後端日誌輸出

---

## 下一步

- 自訂前端樣式和品牌
- 連接自訂資料庫
- 集成到您的工作流程
- 部署到生產環境
