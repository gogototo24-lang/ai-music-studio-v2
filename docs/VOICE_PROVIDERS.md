# 聲線 Provider 架構

更新：2026-10-06

## 目的

保留目前 Render Lite 的穩定性，同時讓《貓掌江湖／喵台灣》能逐步接入更自然的角色聲線與台語。

```text
手機 MV＋聲線工作台
        ↓
AI Music Studio v2 /api/voice/generate
        ↓
VoiceProviderRouter
 ├─ Edge TTS        ← 永遠可用 fallback
 ├─ CosyVoice 3     ← 遠端 GPU adapter
 ├─ PilotTTS        ← 遠端 GPU adapter，zh-minnan 優先測
 └─ GPT-SoVITS      ← 官方 HTTP API，固定角色聲紋
```

## 為什麼不直接裝進 Render Lite

CosyVoice / PilotTTS / GPT-SoVITS 都需要大型模型與較多 RAM／GPU。直接放進目前免費／輕量 Render 服務，會提高啟動失敗、記憶體不足與 MV 編碼互相搶資源的風險。

因此主站只保留 router，模型服務分離。

## Environment Variables

主服務：

```text
VOICE_PRIMARY_PROVIDER=edge
COSYVOICE_API_URL=
PILOTTTS_API_URL=
GPT_SOVITS_API_URL=
```

未設定遠端 URL 時，Edge TTS 照常工作。

## Provider 建議

### Edge TTS
用途：免費 fallback、快速預覽、台灣中文。
正式角色聲紋：不建議當最終版本。

### CosyVoice 3
用途：正式中文角色聲線、情緒、跨語言與方言測試。
程式授權：Apache-2.0。
本 repo 提供：`providers/cosyvoice_adapter.py`。

角色建議：
- 白帝喵尊：低速、威儀、嚴肅
- 月扇影喵：冷靜、克制
- 歲璃喵：空靈、慢速
- 琉璃喵：溫柔

### PilotTTS
用途：第一優先測試 `zh-minnan`。
程式授權：Apache-2.0。
本 repo 提供：`providers/pilottts_adapter.py`。

注意：Minnan 不保證等於自然台灣腔；必須用固定測試句做 A/B 聽感測試。

### GPT-SoVITS
用途：為每個角色建立穩定的 few-shot 聲紋。
程式授權：MIT。
主服務可直接呼叫官方 HTTP API。

目前不把它當台語主力；台語優先 PilotTTS / CosyVoice。

## Reference Voice 規格

只使用你有權使用的原創／授權聲音。不要複製真實人物或未授權表演者的聲音。

建議每位角色建立：

```text
voices/
  white-emperor.wav
  white-emperor.txt
  moonfan.wav
  moonfan.txt
  suili.wav
  suili.txt
```

參考音訊：
- 乾淨單人聲
- 無 BGM
- 無殘響
- 情緒不要過度誇張
- 文字檔與錄音內容一致

## 台語 A/B 測試

固定測試句：

```text
今仔日風真透，咱照家己的步數向前行。
```

比較：
1. Edge：只作華語 baseline
2. PilotTTS：`zh-minnan`
3. CosyVoice：Minnan instruction

評估：
- 台灣腔自然度
- 聲調
- 斷句
- 女性角色音色
- 角色一致性
- 生成速度

勝出者才升成台語 production provider。
