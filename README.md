# Side Hustle · Listing Copilot

> 一句話：Etsy / eBay 賣家的 AI 上架文案 + 定價副手——輸入商品關鍵字，**本地 Gemma** 即刻生成高轉換標題／描述／標籤，全程 100% 離機推理、零 API 成本。

## 功能
- **核心鏈路**：關鍵字 → Ollama 本地模型（JSON mode）→ `{title, description, tags}`
- 平台（Etsy / eBay）與語氣（friendly / professional / playful / luxury）自訂
- 前端**打字機逐字輸出**、右下角固定小字 `100% on-device · Gemma 3 · $0 API`
- 無 Ollama / 模型缺失 / 超時 → 前端友好提示，不白屏；可點「Demo」用離線樣本兜底

## 安裝
```bash
cd sidehustle-listing-copilot
/Users/sum/.workbuddy-ai/binaries/python/versions/3.13.12/bin/python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
/Applications/Ollama.app/Contents/Resources/ollama pull gemma3:4b   # 約 3.4GB
```

## 啟動
```bash
source .venv/bin/activate
uvicorn app.main:app --port 8000
# 瀏覽器開 http://localhost:8000
```

## 環境變數（全部選填，缺省即可跑）
| 變數 | 預設 | 說明 |
|---|---|---|
| `OLLAMA_BASE` | `http://localhost:11434` | Ollama 服務位址 |
| `OLLAMA_MODEL` | `gemma3:4b` | 模型名（可換 `gemma3:1b` / `qwen3.5:9b`） |
| `OLLAMA_TIMEOUT` | `120` | 逾時秒數 |
| `SERPAPI_KEY` | 空 | 填了才查競品價；不填→前端隱藏定價區 |
| `MONGODB_URI` | 空 | 填了寫 Atlas；不填→寫本地 `demo/listings.json` |

## 接通可選整合（SerpApi / MongoDB）
```bash
cp .env.example .env      # .env 已被 .gitignore，唔會 commit
# 編輯 .env：填入 SERPAPI_KEY / MONGODB_URI
uvicorn app.main:app --port 8000 &           # 記得填完 key 要重啟服務
python3 scripts/verify_integrations.py       # 一鍵驗證 6 項（key / health / generate 定價 / save 存儲）
```
全部 PASS = SerpApi 定價層同 MongoDB 存檔真有實證；任何 FAIL 會講明原因。

## Demo Script（評委现场走位，5 步）
```bash
# 1. 起 Ollama（App 已開即跳過）
# 2. 起服務
uvicorn app.main:app --port 8000
# 3. 暖機：起完立即预热一次，避免評委第一次點 Generate 等冷啟動
curl -X POST http://localhost:8000/api/generate -H 'Content-Type: application/json' -d '{"keywords":"ceramic mug","platform":"Etsy","tone":"friendly"}'
```
4. 開前端 `http://localhost:8000`，先按「**Demo**」掣用離線樣本 `demo/sample_outputs.json` 開局（秒開、斷網都得）。
5. 再現場 Generate 一個新 keyword，俾評委睇真係本地模型實跑。

**冷啟動說明**：模型首次加載約 15s、暖機後約 6–7s；demo 時先按步驟 3 預熱或直接用 Demo 掣開場。

## Deploy to Render (demo mode)

This repo ships a [`render.yaml`](./render.yaml) blueprint that deploys the app to Render as a
**demo-mode** web service. Please read the scope carefully — it is deliberately honest about
what the cloud instance can and cannot do:

- **What the cloud instance does:** serves the frontend UI, `GET /health`, and the bundled
  offline sample at `GET /demo/sample_outputs.json`.
- **What it does NOT do:** run the model. Inference is powered by a **local Ollama instance on
  the user's own machine**. Render has no GPU and no local Ollama, so the cloud instance cannot
  reach `OLLAMA_BASE` (`http://localhost:11434`).
- **What happens if you click "Generate" on the cloud instance:** the request fails fast
  (connection refused in a few milliseconds — it does **not** hang), and the UI shows a friendly
  "Ollama offline — use Demo" hint instead of a blank screen. Click **Demo** to load the bundled
  sample (`demo/sample_outputs.json`) and see the full listing output (title / description / tags).

In short: on Render this is a **UI demo / showcase deployment, not a hosted model.** The
`100% on-device` claim stays true — the device is the user's machine, not the cloud.

### Deploy steps (Blueprint)
1. Push this repo to GitHub.
2. In Render: **New + → Blueprint**, connect the repo. Render reads `render.yaml` automatically.
3. Apply. Render builds with `pip install -r requirements.txt` and starts
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Health check is `GET /health` — it always returns `200` (even when Ollama is unreachable), so
   the free-tier health check never fails.
5. Open the service URL → the UI loads. Click **Demo** for the offline sample.

### Optional: real inference in the cloud
If you have a GPU host running Ollama, set these env vars on the Render service and "Generate"
works end-to-end:
- `OLLAMA_BASE` → the public URL of your Ollama host (e.g. `https://ollama.example.com`)
- `OLLAMA_MODEL` → a model available there (e.g. `gemma3:4b`)

### Notes
- Render free tier spins down after ~15 min of inactivity; the next request is a cold start.
- `OLLAMA_BASE` is intentionally unreachable in demo mode so the failure is honest and instant
  (the TCP connect is capped at 5s in `app/ollama_client.py`, so it never hangs).

## 已知缺陷
- SerpApi 競品價需手動填 key 才啟用；無 key 時定價區隱藏（正確降級，非 bug）。
- MongoDB Atlas 需填 `MONGODB_URI`；未填時存檔落本地 JSON（正確降級）。
- 模型首次載入可能稍慢；`OLLAMA_TIMEOUT` 預設 120s 已留足緩衝。

## 為什麼「開源」是核心（三條論據）
1. **零邊際成本**：Gemma 開源模型本地推理，生成 1 萬條 listing 的 API 成本 = $0，純副手生意毛利率極高。
2. **資料不出機**：賣家的商品關鍵字、文案全在 Ollama 離機跑，無隱私洩露風險，對小賣家信任門檻低。
3. **可自托管、可改提示**：開源讓使用者可換模型、改 prompt、塞自己的品牌語氣，形成護城河而非被封鎖在單一 API。
