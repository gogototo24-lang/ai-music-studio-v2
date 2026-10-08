# YuE2 GPU 部署包

這個目錄是 CatPaw 自家完整歌曲 API 的 GPU 部署入口。

## 必要環境變數

```text
MUSIC_SERVICE_TOKEN=<強隨機字串，主 API 與 GPU 服務必須相同>
YUE2_MODEL=m-a-p/YuE2-3B
YUE2_DEVICE=cuda
YUE2_MEMORY_GIB=24
PORT=8010
```

主 AI Music Studio v2 同時設定：

```text
YUE2_API_URL=https://<你的 GPU 服務網址>
MUSIC_SERVICE_TOKEN=<同一個 token>
MUSIC_PRIMARY_PROVIDER=yue2
```

## 安全

- `/health` 可公開供平台做健康檢查。
- `/synthesize` 必須帶 `Authorization: Bearer <MUSIC_SERVICE_TOKEN>`。
- Token 不提交 Git。
- 沒有 Token 時服務拒絕生成。
- C 產線仍不自動發布成品。

## 建置

```bash
docker build -f deploy/yue2/Dockerfile -t catpaw-yue2 .
```

## 執行

```bash
docker run --gpus all -p 8010:8010 \
  -e MUSIC_SERVICE_TOKEN=... \
  -e YUE2_DEVICE=cuda \
  catpaw-yue2
```

第一次啟動需下載 YuE2 模型，冷啟動會比一般 API 久。
