"""Build the messages for Ollama /api/chat, tailored to the Etsy/eBay seller use case."""
from __future__ import annotations

_SYSTEM = (
    "You are an expert e-commerce copywriter and pricing assistant for Etsy and eBay "
    "sellers. You write high-converting product listings. "
    "You MUST respond with a single valid JSON object and nothing else. "
    "The JSON schema is: "
    '{"title": string, "description": string, "tags": string[]}. '
    "Rules: "
    "title must be <= 140 characters and include the most searched keywords; "
    "description must be 2-4 short paragraphs, benefit-driven, with a clear call to action; "
    "tags must be 10-13 lowercase search tags (no '#'), each <= 20 characters."
)

_TONE_HINT = {
    "friendly": "warm, friendly and conversational",
    "professional": "professional, concise and trustworthy",
    "playful": "playful, fun and full of personality",
    "luxury": "premium, elegant and aspirational",
}


def build_messages(keywords: str, platform: str, tone: str) -> list[dict]:
    """Return the messages array used by the Ollama chat call."""
    platform = (platform or "Etsy").strip()
    tone = (tone or "friendly").strip().lower()
    tone_desc = _TONE_HINT.get(tone, _TONE_HINT["friendly"])

    user = (
        f"Product keywords: {keywords}\n"
        f"Marketplace: {platform}\n"
        f"Brand tone: {tone_desc}\n\n"
        f"Write an optimized {platform} listing for this product. "
        "Return ONLY the JSON object with keys title, description, tags."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]
