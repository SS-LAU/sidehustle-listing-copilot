"""Local Ollama inference client: calls /api/chat in JSON mode and returns a structured Listing.

Robustness: Ollama not started / missing model / timeout -> raises OllamaError, which the
layer above turns into a friendly message.
"""
from __future__ import annotations

import json
import os
import re

import httpx

from .prompt_builder import build_messages
from .schemas import Listing

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
REQUEST_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))
# Hard cap on the TCP connect phase only. An unreachable host (e.g. Render has no Ollama)
# must fail fast (~5s) instead of hanging for the whole generation timeout; the read
# timeout stays at REQUEST_TIMEOUT so a reachable-but-slow Ollama can still finish.
CONNECT_TIMEOUT = float(os.getenv("OLLAMA_CONNECT_TIMEOUT", "5"))


class OllamaError(Exception):
    """Raised when an Ollama call fails, with a readable message."""


def _extract_json(text: str) -> dict:
    """Extract JSON from the model output (tolerating surrounding noise / markdown code fences)."""
    text = text.strip()
    # Strip a ```json ... ``` wrapper
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to grab the first { ... } block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def generate_listing(keywords: str, platform: str, tone: str) -> Listing:
    """Call Ollama to generate listing copy and return a Listing. Raises OllamaError on failure."""
    messages = build_messages(keywords, platform, tone)
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.7,
            "num_predict": 700,
        },
    }

    try:
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
    except httpx.ConnectError as e:
        raise OllamaError(
            f"Could not connect to Ollama ({OLLAMA_BASE}). Make sure the Ollama service is running."
        ) from e
    except httpx.ConnectTimeout as e:
        # Connect phase exceeded CONNECT_TIMEOUT (host reachable-but-unresponsive / blackholed).
        raise OllamaError(
            f"Timed out connecting to Ollama ({OLLAMA_BASE}, connect phase >{CONNECT_TIMEOUT:.0f}s)."
        ) from e
    except httpx.TimeoutException as e:
        raise OllamaError(f"Ollama response timed out (>{REQUEST_TIMEOUT:.0f}s); please try again later.") from e

    if resp.status_code == 404:
        raise OllamaError(
            f"Model `{OLLAMA_MODEL}` not found. Run `ollama pull {OLLAMA_MODEL}`."
        )
    if resp.status_code >= 400:
        raise OllamaError(f"Ollama returned error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    content = (data.get("message") or {}).get("content", "")
    if not content:
        raise OllamaError("Ollama returned an empty response.")

    try:
        obj = _extract_json(content)
    except (json.JSONDecodeError, ValueError) as e:
        raise OllamaError(f"Could not parse the model's JSON output: {content[:200]}") from e

    title = str(obj.get("title", "")).strip()
    description = str(obj.get("description", "")).strip()
    tags = obj.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,\n]", tags) if t.strip()]
    tags = [str(t).strip().lstrip("#").lower() for t in tags if str(t).strip()]

    if not title or not description:
        raise OllamaError("Model output is missing title or description.")

    return Listing(title=title, description=description, tags=tags)


def ollama_health() -> dict:
    """Check whether the Ollama service and the target model are ready."""
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            names = [m["name"] for m in resp.json().get("models", [])]
        return {"up": True, "model_ready": OLLAMA_MODEL in names, "model": OLLAMA_MODEL, "models": names}
    except Exception as e:  # noqa: BLE001
        return {"up": False, "model_ready": False, "model": OLLAMA_MODEL, "error": str(e)}
