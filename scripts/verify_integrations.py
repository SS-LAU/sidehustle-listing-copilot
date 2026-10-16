#!/usr/bin/env python3
"""一鍵驗證 Listing Copilot 嘅可選整合（SerpApi 定價層 / MongoDB 存檔）。

用法：
    python3 scripts/verify_integrations.py [--base http://localhost:8000]

檢查項目：
    1. .env 入面 SERPAPI_KEY / MONGODB_URI 有冇填
    2. GET  /health          → serpapi_enabled / storage 係咩模式
    3. POST /api/generate    → price_stats 有冇真數據（證明 SerpApi 接通）
    4. POST /api/save        → storage 係 mongodb 定 local-json（證明 MongoDB 接通）

任何一項 FAIL 都會講明原因。全部 PASS →  exit 0。
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

KEYWORDS = "handmade ceramic mug, minimalist, gift"

# Resolve .env against THIS script's project root, never the current working
# directory. Running the script from another cwd (e.g. ~) used to silently
# report the keys as "missing" because it looked for ./.env.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env_keys(path=None):
    path = Path(path) if path else _ENV_PATH
    keys = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        return {}
    return keys


def req(method, base, path, body=None, timeout=180):
    url = base.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    args = ap.parse_args()
    base = args.base
    results = []

    env_found = _ENV_PATH.exists()
    print(f".env path: {_ENV_PATH}  [{'found' if env_found else 'NOT FOUND'}]")
    print(f"API base : {base}\n")

    env = load_env_keys()
    missing = "" if env_found else f"（搵唔到 {_ENV_PATH}）"
    serp_key = bool(env.get("SERPAPI_KEY"))
    mongo_uri = bool(env.get("MONGODB_URI"))
    results.append((".env SERPAPI_KEY 已填", serp_key,
                    f"未填{missing} → 定價層會自動隱藏（要報 SerpApi 分類必須填）" if not serp_key else "OK"))
    results.append((".env MONGODB_URI 已填", mongo_uri,
                    f"未填{missing} → 存檔會降級到本地 JSON（要報 MongoDB 分類必須填）" if not mongo_uri else "OK"))

    try:
        health = req("GET", base, "/health", timeout=10)
    except Exception as e:
        print(f"FAIL: 連唔到 {base}（服務起咗未？uvicorn app.main:app --port 8000）\n  {e}")
        return 1
    serp_on = bool(health.get("serpapi_enabled"))
    storage = health.get("storage", "?")
    results.append(("/health serpapi_enabled", serp_on,
                    "服務讀到 SERPAPI_KEY" if serp_on else "服務未讀到 key（.env 填咗要重啟服務）"))
    results.append(("/health storage 模式", storage in ("mongodb", "mongo"),
                    f"storage={storage}（mongodb=接通 Atlas；local-json=未接）"))

    try:
        gen = req("POST", base, "/api/generate",
                  {"keywords": KEYWORDS, "platform": "Etsy", "tone": "friendly"})
        ps = gen.get("price_stats")
        results.append(("/api/generate price_stats 有數據", bool(ps),
                        "SerpApi 真接通" if ps else "price_stats=null → SerpApi 未接通（key 未填或查詢失敗）"))
        print(f"  generate: elapsed={gen.get('elapsed_sec')}s model={gen.get('model')} price_stats={ps}")
    except Exception as e:
        results.append(("/api/generate", False, f"呼叫失敗：{e}"))

    try:
        save = req("POST", base, "/api/save",
                   {"keywords": KEYWORDS, "title": "verify run", "description": "n/a",
                    "tags": ["verify"], "platform": "Etsy"})
        st = save.get("storage")
        results.append(("/api/save 落入正確存儲", st in ("mongodb", "mongo"),
                        f"storage={st}（mongodb=入咗 Atlas；local-json=本地兜底）"))
    except Exception as e:
        results.append(("/api/save", False, f"呼叫失敗：{e}"))

    print()
    ok = True
    for name, passed, note in results:
        print(f"{'PASS' if passed else 'FAIL'}  {name}  — {note}")
        ok = ok and passed
    print()
    print("結論：" + ("全部接通，Prize Categories（SerpApi / MongoDB）有實證支撐。"
                   if ok else "有項目未接通——見上面 FAIL 原因。"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
