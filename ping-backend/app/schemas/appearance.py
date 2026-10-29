import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class WidgetAppearance(BaseModel):
    """What the widget looks like. Stored as JSONB on the bot; every field has
    a default so older rows keep working when a field is added."""

    title: str = Field(default="Assistant", max_length=60)
    welcome: str = Field(default="Hi! Ask me anything.", max_length=500)
    placeholder: str = Field(default="Ask a question…", max_length=80)
    accent: str = "#7C3AED"
    position: Literal["right", "left"] = "right"
    launcher: Literal["chat", "spark", "help"] = "chat"
    suggestions: list[str] = Field(default_factory=list, max_length=4)
    show_sources: bool = True
    show_branding: bool = True
    theme: Literal["dark", "light"] = "dark"

    @field_validator("accent")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not _HEX.match(v):
            raise ValueError("accent must be a #RRGGBB hex color")
        return v.upper()

    @field_validator("suggestions")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        out = [s.strip()[:120] for s in v if s and s.strip()]
        return out[:4]
