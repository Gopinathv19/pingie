import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.enums import SourceStatus, SourceType


class SourceRead(BaseModel):
    id: uuid.UUID
    name: str
    type: SourceType
    status: SourceStatus
    error: str | None
    progress: int
    chunks: int
    size_bytes: int | None
    page_count: int | None
    url: str | None
    updated_at: datetime


class SourceSummary(BaseModel):
    total: int
    ready: int
    failed: int
    indexing: int
    chunks: int
    last_sync: datetime | None


class SourceList(BaseModel):
    items: list[SourceRead]
    summary: SourceSummary


class UrlSourceCreate(BaseModel):
    url: str = Field(min_length=3, max_length=2048)
    kind: Literal["url", "sitemap"] = "url"
