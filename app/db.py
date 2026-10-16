"""Storage layer: writes to Atlas when MONGODB_URI is set, otherwise to the local demo/listings.json.

With no URI it always succeeds (no-op degradation), so the demo's Save button always gives feedback.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from .schemas import Listing

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB = os.getenv("MONGODB_DB", "sidehustle")
_LOCAL_PATH = Path(__file__).resolve().parent.parent / "demo" / "listings.json"


def _save_local(listing: Listing) -> str:
    """Write the local JSON file and return the id."""
    _LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = []
    if _LOCAL_PATH.exists():
        try:
            records = json.loads(_LOCAL_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            records = []
    new_id = uuid.uuid4().hex[:12]
    records.append(
        {
            "id": new_id,
            "title": listing.title,
            "description": listing.description,
            "tags": listing.tags,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "storage": "local-json",
        }
    )
    _LOCAL_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return new_id


def save_listing(listing: Listing) -> str:
    """Save a listing and return its id. Prefers Mongo; on failure or no URI -> local JSON."""
    if MONGODB_URI:
        try:
            from pymongo import MongoClient

            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            col = client[MONGODB_DB]["listings"]
            doc = {
                "title": listing.title,
                "description": listing.description,
                "tags": listing.tags,
                "saved_at": time.time(),
                "storage": "mongodb",
            }
            result = col.insert_one(doc)
            return str(result.inserted_id)
        except Exception:  # noqa: BLE001 -- fall back to local storage if Mongo fails
            return _save_local(listing)
    return _save_local(listing)


def storage_backend() -> str:
    """Report the current storage backend, shown by /health."""
    if MONGODB_URI:
        try:
            from pymongo import MongoClient

            MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000).admin.command("ping")
            return "mongodb"
        except Exception:  # noqa: BLE001
            return "local-json (mongo unreachable)"
    return "local-json"
