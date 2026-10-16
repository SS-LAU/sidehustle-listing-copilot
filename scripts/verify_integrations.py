#!/usr/bin/env python3
"""One-shot verifier for Listing Copilot's optional integrations (SerpApi pricing / MongoDB storage).

Usage:
    python3 scripts/verify_integrations.py [--base http://localhost:8000]

Checks:
    1. Whether SERPAPI_KEY / MONGODB_URI are set in .env
    2. GET  /health          -> serpapi_enabled / storage mode
    3. POST /api/generate    -> whether price_stats has real data (proves SerpApi is wired up)
    4. POST /api/save        -> whether storage is mongodb or local-json (proves MongoDB is wired up)

Any FAIL explains why. All PASS -> exit 0.
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
    missing = "" if env_found else f" ({_ENV_PATH} not found)"
    serp_key = bool(env.get("SERPAPI_KEY"))
    mongo_uri = bool(env.get("MONGODB_URI"))
    results.append((".env SERPAPI_KEY set", serp_key,
                    f"not set{missing} -> the pricing layer is auto-hidden (fill it to qualify for the SerpApi category)" if not serp_key else "OK"))
    results.append((".env MONGODB_URI set", mongo_uri,
                    f"not set{missing} -> saves fall back to local JSON (fill it to qualify for the MongoDB category)" if not mongo_uri else "OK"))

    try:
        health = req("GET", base, "/health", timeout=10)
    except Exception as e:
        print(f"FAIL: cannot reach {base} (is the server running? uvicorn app.main:app --port 8000)\n  {e}")
        return 1
    serp_on = bool(health.get("serpapi_enabled"))
    storage = health.get("storage", "?")
    results.append(("/health serpapi_enabled", serp_on,
                    "the server read SERPAPI_KEY" if serp_on else "the server did not read the key (restart the server after editing .env)"))
    results.append(("/health storage mode", storage in ("mongodb", "mongo"),
                    f"storage={storage} (mongodb=Atlas wired up; local-json=not wired up)"))

    try:
        gen = req("POST", base, "/api/generate",
                  {"keywords": KEYWORDS, "platform": "Etsy", "tone": "friendly"})
        ps = gen.get("price_stats")
        results.append(("/api/generate price_stats has data", bool(ps),
                        "SerpApi is really wired up" if ps else "price_stats=null -> SerpApi not wired up (key missing or query failed)"))
        print(f"  generate: elapsed={gen.get('elapsed_sec')}s model={gen.get('model')} price_stats={ps}")
    except Exception as e:
        results.append(("/api/generate", False, f"call failed: {e}"))

    try:
        save = req("POST", base, "/api/save",
                   {"keywords": KEYWORDS, "title": "verify run", "description": "n/a",
                    "tags": ["verify"], "platform": "Etsy"})
        st = save.get("storage")
        results.append(("/api/save writes to the right storage", st in ("mongodb", "mongo"),
                        f"storage={st} (mongodb=written to Atlas; local-json=local fallback)"))
    except Exception as e:
        results.append(("/api/save", False, f"call failed: {e}"))

    print()
    ok = True
    for name, passed, note in results:
        print(f"{'PASS' if passed else 'FAIL'}  {name}  — {note}")
        ok = ok and passed
    print()
    print("Conclusion: " + ("everything wired up — the Prize Categories (SerpApi / MongoDB) are backed by evidence."
                   if ok else "some items are not wired up — see the FAIL reasons above."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
