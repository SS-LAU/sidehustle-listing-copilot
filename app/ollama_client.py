"""Ollama 本地推理客戶端：呼叫 /api/chat，JSON mode，回傳結構化 Listing。

健壯性：Ollama 未啟動 / 模型缺失 / 超時 → 拋出 OllamaError，由上層轉成友善訊息。
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
    """Ollama 呼叫失敗時拋出，附帶可讀訊息。"""


def _extract_json(text: str) -> dict:
    """從模型輸出抽出 JSON（容忍前後雜訊 / markdown code fence）。"""
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 嘗試抓第一個 { ... } 區塊
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def generate_listing(keywords: str, platform: str, tone: str) -> Listing:
    """呼叫 Ollama 生成上架文案，回傳 Listing。失敗拋 OllamaError。"""
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
            f"無法連線 Ollama（{OLLAMA_BASE}）。請確認 Ollama 服務已啟動。"
        ) from e
    except httpx.ConnectTimeout as e:
        # Connect phase exceeded CONNECT_TIMEOUT (host reachable-but-unresponsive / blackholed).
        raise OllamaError(
            f"連線 Ollama 逾時（{OLLAMA_BASE}，連線階段 >{CONNECT_TIMEOUT:.0f}s）。"
        ) from e
    except httpx.TimeoutException as e:
        raise OllamaError(f"Ollama 回應超時（>{REQUEST_TIMEOUT:.0f}s），請稍後重試。") from e

    if resp.status_code == 404:
        raise OllamaError(
            f"模型 `{OLLAMA_MODEL}` 不存在。請執行 `ollama pull {OLLAMA_MODEL}`。"
        )
    if resp.status_code >= 400:
        raise OllamaError(f"Ollama 回傳錯誤 {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    content = (data.get("message") or {}).get("content", "")
    if not content:
        raise OllamaError("Ollama 回傳空內容。")

    try:
        obj = _extract_json(content)
    except (json.JSONDecodeError, ValueError) as e:
        raise OllamaError(f"無法解析模型輸出的 JSON：{content[:200]}") from e

    title = str(obj.get("title", "")).strip()
    description = str(obj.get("description", "")).strip()
    tags = obj.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,\n]", tags) if t.strip()]
    tags = [str(t).strip().lstrip("#").lower() for t in tags if str(t).strip()]

    if not title or not description:
        raise OllamaError("模型輸出缺少 title 或 description。")

    return Listing(title=title, description=description, tags=tags)


def ollama_health() -> dict:
    """檢查 Ollama 服務與目標模型是否就緒。"""
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            names = [m["name"] for m in resp.json().get("models", [])]
        return {"up": True, "model_ready": OLLAMA_MODEL in names, "model": OLLAMA_MODEL, "models": names}
    except Exception as e:  # noqa: BLE001
        return {"up": False, "model_ready": False, "model": OLLAMA_MODEL, "error": str(e)}
