# Side Hustle · Listing Copilot

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

> In one line: an AI listing-copy + pricing copilot for Etsy / eBay sellers — type in product keywords and a **local Gemma** model instantly writes a high-converting title / description / tags, running 100% on-device with zero API cost.

## Features
- **Core pipeline**: keywords → local Ollama model (JSON mode) → `{title, description, tags}`
- 10–13 lowercase search tags, each ≤ 20 characters, with no `#` (Etsy search doesn't treat hashtags as tags, and eBay has no tag field at all). The UI renders them as `#chip` labels because that's how people read them, but the underlying values are exactly what a seller pastes into Etsy.
- Customisable marketplace (Etsy / eBay) and brand tone (friendly / professional / playful / luxury)
- Frontend **typewriter output**, with a fixed `100% on-device · Gemma 3 · $0 API` badge in the bottom-right corner
- No Ollama / missing model / timeout → friendly frontend message, never a blank screen; the **Demo** button loads a bundled offline sample as a fallback

## Install
```bash
cd sidehustle-listing-copilot
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
ollama pull gemma3:4b            # ~3.4 GB
```

## Run
```bash
source .venv/bin/activate
uvicorn app.main:app --port 8000
# open http://localhost:8000 in your browser
```

## Environment variables (all optional — the app runs without any of them)
| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gemma3:4b` | Model name (can switch to `gemma3:1b` / `qwen3.5:9b`) |
| `OLLAMA_TIMEOUT` | `120` | Request timeout in seconds |
| `SERPAPI_KEY` | empty | Set it to look up competitor prices; if empty, the pricing block is hidden in the frontend |
| `MONGODB_URI` | empty | Set it to write to Atlas; if empty, saves go to the local `demo/listings.json` |
| `MONGODB_DB` | `sidehustle` | MongoDB database name |

## Wiring up the optional integrations (SerpApi / MongoDB)
```bash
cp .env.example .env      # .env is gitignored, so it is never committed
# edit .env: fill in SERPAPI_KEY / MONGODB_URI
uvicorn app.main:app --port 8000 &           # remember to restart the server after adding keys
python3 scripts/verify_integrations.py       # one-shot check of 6 items (keys / health / generate pricing / save storage)
```
All PASS means the SerpApi pricing layer and MongoDB storage are genuinely wired up; any FAIL states the reason.

## Try the demo in 5 steps
```bash
# 1. Start Ollama (skip if the desktop app is already running)
# 2. Start the server
uvicorn app.main:app --port 8000
# 3. Warm-up: fire one request right after start-up, so the first click isn't a cold start
curl -X POST http://localhost:8000/api/generate -H 'Content-Type: application/json' -d '{"keywords":"ceramic mug","platform":"Etsy","tone":"friendly"}'
```
4. Open `http://localhost:8000` and click **Demo** first to open with the offline sample `demo/sample_outputs.json` (instant, works even offline).
5. Then generate a fresh listing with a new keyword, so you can see the local model run for real.

**Cold start**: the model takes ~15s to load the first time and ~6–7s once warm; warm it up with step 3 or open from the Demo button.

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

### Optional: turn on SerpApi + MongoDB on the deployed instance
Both are cloud services, so — unlike Ollama — they *do* work from Render. They are declared in
`render.yaml` with `sync: false`, which means the value is **never committed to git**: Render
prompts for it in the dashboard on sync and stores it encrypted afterwards.

Set them under **Dashboard → your service → Environment**:

| Variable | What it turns on |
|---|---|
| `SERPAPI_KEY` | Live competitor pricing (Google Shopping) rendered next to the generated listing |
| `MONGODB_URI` | The **Save** button writes to MongoDB Atlas instead of the local JSON fallback |

Leave either one blank to keep the graceful-degradation path. To check what the deployed
instance actually reports:

```bash
curl https://<your-service>.onrender.com/health
# "storage": "mongodb"      <- MongoDB Atlas is wired up
# "serpapi_enabled": true   <- SerpApi is wired up
```

### Optional: real inference in the cloud
If you have a GPU host running Ollama, set these env vars on the Render service and "Generate"
works end-to-end:
- `OLLAMA_BASE` → the public URL of your Ollama host (e.g. `https://ollama.example.com`)
- `OLLAMA_MODEL` → a model available there (e.g. `gemma3:4b`)

### Notes
- Render free tier spins down after ~15 min of inactivity; the next request is a cold start.
  `.github/workflows/keepalive.yml` pings `/health` every 5 minutes to keep the hosted demo
  responsive — delete that workflow if you'd rather let the instance sleep.
- `OLLAMA_BASE` is intentionally unreachable in demo mode so the failure is honest and instant
  (the TCP connect is capped at 5s in `app/ollama_client.py`, so it never hangs).

## Known limitations
- SerpApi competitor pricing needs a key to be enabled; without one the pricing block is hidden (intended graceful degradation, not a bug).
- MongoDB Atlas needs `MONGODB_URI`; without it, saves fall back to local JSON (intended graceful degradation).
- The model can be slow to load the first time; the default `OLLAMA_TIMEOUT` of 120s leaves plenty of headroom.

## Why open-source is core to this project
1. **Zero marginal cost**: the open-source Gemma model runs locally, so generating 10,000 listings costs $0 in API fees — a side-hustle tool with very high gross margin.
2. **No prompt ever reaches a hosted LLM**: a seller's keywords and copy run entirely through local Ollama, so there is no "we may train on your prompts" exposure and the trust bar for small sellers stays low. The only outbound traffic is the two optional integrations — a SerpApi price lookup and a MongoDB save — and both stay off until you add keys.
3. **Self-hostable and prompt-editable**: being open-source lets users swap models, edit the prompt and inject their own brand tone — a moat, rather than being locked into a single API.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, ship it, sell it.
