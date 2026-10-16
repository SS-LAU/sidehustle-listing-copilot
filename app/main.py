"""FastAPI app: core pipeline POST /api/generate, plus GET /, GET /health and POST /api/save."""
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
    """Serve the single-file frontend."""
    return FileResponse(_STATIC / "index.html")


@app.get("/demo/sample_outputs.json")
def demo_sample() -> FileResponse:
    """Offline fallback: serve demo/sample_outputs.json to the frontend Demo button."""
    path = Path(__file__).resolve().parent.parent / "demo" / "sample_outputs.json"
    if not path.exists():
        return FileResponse(content=b"[]", media_type="application/json")
    return FileResponse(path, media_type="application/json")


@app.get("/health")
def health() -> dict:
    """Health check: Ollama status + storage backend + whether a SerpApi key is set."""
    return {
        "status": "ok",
        "ollama": ollama_health(),
        "storage": db.storage_backend(),
        "serpapi_enabled": bool(serp_client.SERPAPI_KEY),
    }


@app.post("/api/generate")
def generate(req: GenerateRequest) -> JSONResponse:
    """Core pipeline: keywords -> Ollama generation -> competitor prices (optional)."""
    start = time.time()
    try:
        listing = generate_listing(req.keywords, req.platform, req.tone)
    except OllamaError as e:
        # Friendly error: HTTP 503 so the frontend shows a hint instead of a blank screen.
        return JSONResponse(
            status_code=503,
            content={"error": str(e), "detail": "The local model is temporarily unavailable; please retry or use the cached demo."},
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
    """Save endpoint: the frontend sends back a generated listing to store in Mongo / local JSON."""
    from .schemas import Listing

    listing = Listing(title=req.title, description=req.description, tags=req.tags)
    try:
        new_id = db.save_listing(listing)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"error": f"Save failed: {e}"})
    return JSONResponse(
        content={"ok": True, "id": new_id, "storage": db.storage_backend()}
    )
