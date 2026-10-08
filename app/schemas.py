# -*- coding: utf-8 -*-
"""接口出入参模型。"""
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    document_ids: Optional[list[str]] = Field(default=None, max_length=30)


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None
    sources: list = []
    engine: str = "langchain"   # langchain | crew
    run_id: Optional[str] = None
    stop_reason: Optional[str] = None
    review_approved: bool = False
    citations: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    model_calls: int = 0
    tool_calls: int = 0
    used_crew: bool = False
    cache_hit: bool = False


class IngestResponse(BaseModel):
    file_name: str
    chunks: int
    total_chunks: int


class StatsResponse(BaseModel):
    total_chunks: int
    llm_model: str
    embedding_model: str
    use_crew: bool
    crew_available: bool
    hybrid_enabled: bool = True
    bm25_ready: bool = False
    rerank_enabled: bool = False
    cache_enabled: bool = False
    cache_size: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_threshold: float = 0.0
    ratelimit_enabled: bool = False
    ratelimit_per_minute: int = 0
    ratelimit_blocked: int = 0
