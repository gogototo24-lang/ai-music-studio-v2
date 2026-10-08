# CatPaw 自家 Music API v2.3

目標：不再依賴 ElevenLabs 才能生成音樂。

## 架構

```text
GitHub Pages / CatPaw Factory C 線
        ↓
AI Music Studio v2
POST /api/music/generate
        ↓
MusicProviderRouter
 ├─ MusicGen local     → BGM / instrumental
 ├─ YuE2 self-hosted   → 完整歌曲、歌詞、人聲
 └─ ACE-Step adapter   → 快速歌曲／音樂生成候選
```

## 重要區分

MusicGen 是 BGM 模型，不保證唱指定歌詞。

要做「舞魅喵角色歌」這類完整歌曲，正式路徑優先：

```text
YuE2 self-hosted
```

YuE2 程式授權為 Apache-2.0；GPU 模型服務與主 Render Lite 分開部署。

## Main API 環境變數

```text
MUSIC_PRIMARY_PROVIDER=musicgen
YUE2_API_URL=
ACESTEP_API_URL=
```

未設定 GPU provider 時，主 API 不會壞掉，仍可使用 MusicGen / fallback。

## API

### Provider 狀態

```
GET /api/music/providers
```

### 生成

```
POST /api/music/generate
Content-Type: application/json
```

範例：

```json
{
  "provider": "yue2",
  "title": "舞魅喵・一舞封塵",
  "style": "dark cinematic wuxia, female vocal, pipa, guzheng, war drums",
  "lyrics": "[Verse]\n月落無聲...\n[Chorus]\n一舞封塵...",
  "duration": 60,
  "seed": 42
}
```

## YuE2 GPU service

檔案：

```
providers/yue2_music_api.py
requirements-yue2.txt
```

啟動：

```bash
pip install -r requirements-yue2.txt
uvicorn providers.yue2_music_api:app --host 0.0.0.0 --port 8010
```

主站設定：

```
YUE2_API_URL=https://your-gpu-host
MUSIC_PRIMARY_PROVIDER=yue2
```

## 成本策略

這套 API 本身不收第三方 API 費；真正成本是你使用的 GPU 主機／RunningHub GPU 算力。

建議：
1. MusicGen / Mock 先驗 prompt。
2. YuE2 單首低成本測試。
3. 成功歌曲才進 MV。
4. 不自動重跑，不自動發布。
