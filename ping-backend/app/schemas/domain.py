import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DomainCreate(BaseModel):
    host: str = Field(min_length=3, max_length=255)


class DomainRead(BaseModel):
    id: uuid.UUID
    host: str
    receiving_traffic: bool
    last_seen_at: datetime | None
    created_at: datetime


class InstallInfo(BaseModel):
    bot_id: str
    public_key: str
    script_url: str
    snippet_html: str
    detected: bool
    detected_host: str | None
    detected_at: datetime | None
