"""SerpApi competitor-price lookup add-on.

With no SERPAPI_KEY it returns None -> the frontend hides the pricing block
(graceful degradation, never blocks the core path).
"""
from __future__ import annotations

import os
import statistics

import httpx

from .schemas import PriceStats

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
SERPAPI_URL = "https://serpapi.com/search.json"


def get_competitor_prices(query: str) -> PriceStats | None:
    """Look up competitor prices and return stats. No key or a failure -> None."""
    if not SERPAPI_KEY:
        return None

    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": 20,
        "hl": "en",
        "gl": "us",
    }
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(SERPAPI_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:  # noqa: BLE001 -- any failure degrades to None
        return None

    prices: list[float] = []
    for item in data.get("shopping_results", []):
        raw = item.get("extracted_price")
        if raw is None:
            raw = item.get("price")
        try:
            val = float(str(raw).replace("$", "").replace(",", "").strip())
            if val > 0:
                prices.append(val)
        except (TypeError, ValueError):
            continue

    if not prices:
        return None

    return PriceStats(
        min=round(min(prices), 2),
        max=round(max(prices), 2),
        median=round(statistics.median(prices), 2),
        count=len(prices),
    )
