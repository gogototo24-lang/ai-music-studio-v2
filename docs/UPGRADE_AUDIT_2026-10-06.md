# GitHub 專案升級檢查

日期：2026-10-06

## 結論

| Repo | 狀態 | 建議 |
|---|---|---|
| ai-music-studio | 需更新文件 | README 原先停在 v0.1，但 index.html 已是 v1.0 |
| ai-music-studio-v2 | 可繼續使用 | Runtime 2.0.1；補文件與 dependency lock |
| threads-scheduler | 核心可用 | Wrangler lock 已是 4.135.0；影片正式發布仍缺一段 |
| codexskills | 需補技能 | 新增 video-prompt-builder |

## ai-music-studio

### 發現
- `index.html` 顯示 v1.0。
- 原 README 還描述 v0.1。
- GitHub Pages workflow 使用：
  - actions/checkout@v4
  - actions/configure-pages@v5
  - actions/upload-pages-artifact@v3
  - actions/deploy-pages@v4
- 最近可讀到的 Pages deployment 為 success。

### 動作
更新 README 與專案定位；Pages workflow 暫不改。

## ai-music-studio-v2

### 發現
- `app.py` 版本為 2.0.1。
- requirements 使用最低版本條件，部署時可能取得較新相依套件。
- 目前沒有明確 production lock，因此可重現性不足。

### 動作
- 不為了版本號強制升級主程式。
- 下一次穩定部署後建立 pinned production requirements。
- 先補影音串聯文件。
- Torch / AudioCraft / Demucs 不做未測試的大版本跳升。

## threads-scheduler

### 發現
- `package.json` 使用 `wrangler ^4.0.0`。
- `package-lock.json` 已鎖到 Wrangler 4.135.0。
- provider 已有 mock / OpenAI / PixVerse。
- video job 會生成，但正式 publisher 目前只映射為 IMAGE 或 TEXT。

### 動作
- Wrangler 暫不升級。
- 下一階段補 Higgsfield adapter。
- VIDEO 正式發布端先核實 Threads 官方 API 再改 production code。

## codexskills

### 發現
- 原 manifest 沒有 `video-prompt-builder`。

### 動作
新增自有 skill；其他外部 skill 不做盲目批次更新。
