# AI Music Studio v2 — 貓掌影音音樂工作室

這個版本把原本的 FastAPI 音訊原型與「自動 MV」合成在同一套後端。

## 已整合
- 原創角色歌詞：國語／台語模板／混合
- 女性角色口白：Edge TTS + 劇場混響
- 本機配樂：有 MusicGen 時使用 MusicGen；沒有時明確退回 FFmpeg「測試配樂」
- 音軌分離：有 Demucs 時使用 Demucs；沒有時使用 FFmpeg fallback
- 真正 side-chain ducking 混音
- 自動 MV：圖片／影片片段 + 音訊 + 歌詞字幕 → 9:16 / 16:9 MP4
- CORS：已預設允許 `https://gogototo24-lang.github.io`
- 每次輸出使用唯一檔名，避免互相覆蓋
- 上傳副檔名與檔案大小限制

## 重要差別
1. `edge-tts` 是「口白朗讀」，不是 AI 歌唱。
2. `MusicGen` 是配樂模型，不會替歌詞唱歌。
3. `video_engine.py` 是自動剪輯與字幕合成；它不會憑空生成角色動畫。角色動畫仍需先由影片生成工具產生片段，再交給本工具剪輯。
4. 台語模板可產生台文混合歌詞，但 Edge TTS 的 zh-TW 聲音不是專門的台語 TTS，台語口白品質要另外接真正支援台語的語音模型才會更自然。

## 快速啟動
系統必須先有 **FFmpeg**。

```bash
pip install -r requirements.txt
python app.py
```

開啟：
`http://localhost:8000`

## 啟用 MusicGen / Demucs（選用）
```bash
pip install -r requirements-ai.txt
```

這兩個功能需要較多 RAM / 硬碟，MusicGen 在 GPU 環境會比較實用。

## Docker
```bash
docker build -t ai-music-studio-v2 .
docker run --rm -p 8000:8000 ai-music-studio-v2
```

Docker 預設是 Lite 模式：FFmpeg + Edge TTS。若要加入 MusicGen / Demucs，建議另外做 GPU 映像或在較大的主機安裝 `requirements-ai.txt`。

## 主要 API
- `GET /health`
- `POST /api/lyrics/generate`
- `POST /api/voice/generate`
- `POST /api/music/generate`
- `POST /api/extract`
- `POST /api/mix`
- `POST /api/mv/render`

## 建議部署
一般小型雲端主機可以跑 Lite 模式；MusicGen / Demucs 屬重型 AI 工作負載，不適合 Cloudflare Worker。前端可以繼續放 GitHub Pages，Python 後端另放可執行 FFmpeg 的服務。
