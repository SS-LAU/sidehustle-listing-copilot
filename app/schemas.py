"""Pydantic 資料模型：定義 API 出入參與 Listing 結構。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """前端傳入的生成請求。"""

    keywords: str = Field(..., min_length=1, description="商品關鍵字，逗號分隔")
    platform: str = Field(default="Etsy", description="平台：Etsy 或 eBay")
    tone: str = Field(default="friendly", description="語氣：friendly / professional / playful / luxury")


class Listing(BaseModel):
    """Ollama 生成的結構化上架文案。"""

    title: str = Field(..., description="商品標題")
    description: str = Field(..., description="商品描述")
    tags: list[str] = Field(default_factory=list, description="搜尋標籤")


class PriceStats(BaseModel):
    """競品價格統計（SerpApi 加層，無 key 時為 None）。"""

    min: Optional[float] = None
    max: Optional[float] = None
    median: Optional[float] = None
    count: int = 0


class SaveRequest(BaseModel):
    """前端把已生成的 listing 內容送回存檔。"""

    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    tags: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    """API 回傳：生成文案 + 可選競品價 + 可選存檔 id。"""

    listing: Listing
    price_stats: Optional[PriceStats] = None
    saved_id: Optional[str] = None
    elapsed_sec: Optional[float] = None
    model: Optional[str] = None
    error: Optional[str] = None
