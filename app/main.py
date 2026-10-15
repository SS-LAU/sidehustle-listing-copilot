"""FastAPI 主程式：核心鏈路 POST /api/generate、GET /、GET /health、POST /api/save。"""
from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402

from . import db, serp_client  # noqa: E402
from .ollama_client import OllamaError, generate_listing, ollama_health  # noqa: E402
from .schemas import GenerateRequest, GenerateResponse, SaveRequest  # noqa: E402

app = FastAPI(title="Side Hustle Listing Copilot", version="0.1.0")

_STATIC = Path(__file__).resolve().parent / "static"


@app.get("/")
def index() -> FileResponse:
    """Serve 單檔前端。"""
    return FileResponse(_STATIC / "index.html")


@app.get("/demo/sample_outputs.json")
def demo_sample() -> FileResponse:
    """離線兜底：提供 demo/sample_outputs.json 給前端 Demo 按鈕。"""
    path = Path(__file__).resolve().parent.parent / "demo" / "sample_outputs.json"
    if not path.exists():
        return FileResponse(content=b"[]", media_type="application/json")
    return FileResponse(path, media_type="application/json")


@app.get("/health")
def health() -> dict:
    """健康檢查：Ollama 狀態 + 存檔後端 + 是否有 SerpApi key。"""
    return {
        "status": "ok",
        "ollama": ollama_health(),
        "storage": db.storage_backend(),
        "serpapi_enabled": bool(serp_client.SERPAPI_KEY),
    }


@app.post("/api/generate")
def generate(req: GenerateRequest) -> JSONResponse:
    """核心鏈路：關鍵字 → Ollama 生成 → 競品價（可選）。"""
    start = time.time()
    try:
        listing = generate_listing(req.keywords, req.platform, req.tone)
    except OllamaError as e:
        # 友善錯誤：HTTP 503，前端顯示提示不白屏
        return JSONResponse(
            status_code=503,
            content={"error": str(e), "detail": "本地模型暫時無法回應，請重試或改用快取 demo。"},
        )

    price_stats = serp_client.get_competitor_prices(req.keywords)
    elapsed = round(time.time() - start, 2)

    return JSONResponse(
        content=GenerateResponse(
            listing=listing,
            price_stats=price_stats,
            elapsed_sec=elapsed,
            model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
        ).model_dump()
    )


@app.post("/api/save")
def save(req: SaveRequest) -> JSONResponse:
    """存檔端點：前端把已生成的 listing 送回，存入 Mongo/本地 JSON。"""
    from .schemas import Listing

    listing = Listing(title=req.title, description=req.description, tags=req.tags)
    try:
        new_id = db.save_listing(listing)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": f"存檔失敗：{e}"})
    return JSONResponse(
        content={"ok": True, "id": new_id, "storage": db.storage_backend()}
    )
