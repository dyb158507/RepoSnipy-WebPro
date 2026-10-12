# -*- coding: utf-8 -*-
"""接口的请求 / 响应数据结构。"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RepoCard(BaseModel):
    """列表里的一张仓库卡片。"""

    name: str
    github_url: str
    stars: int = 0
    license: str = ""
    topics: List[str] = Field(default_factory=list)
    available_layers: List[str] = Field(default_factory=list)
    score: Optional[float] = None


class SearchResponse(BaseModel):
    name: str
    mode: str
    limit: int
    query: RepoCard
    results: List[RepoCard]


class IndexRequest(BaseModel):
    """新增 / 更新仓库到索引。"""

    name: str = Field(..., description="owner/repo")
    github_token: Optional[str] = Field(default=None, description="GitHub Personal Access Token")


class IndexResponse(BaseModel):
    name: str


class LayerInfo(BaseModel):
    key: str
    field: str
    dim: int
    covered: int
    total: int
    ratio: float


class MetaResponse(BaseModel):
    status: str
    message: str
    dataset: str
    error: Optional[str] = None
    index_size: Optional[int] = None
    raw_index_size: Optional[int] = None
    load_seconds: Optional[float] = None
    layers: Optional[List[LayerInfo]] = None
    samples: Optional[List[str]] = None
    device: Optional[str] = None
    default_mode: Optional[str] = None
    domain_weights: Optional[Dict[str, float]] = None
    drop_components: Optional[int] = None
