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
    # Visitors can browse the bot's web pages and team answers.
    help_center_enabled: bool = True

    # Custom design (paid plans only; see PRO_FIELDS). Free widgets render the defaults.
    layout: Literal["classic", "welcome", "compact"] = "classic"
    header_style: Literal["solid", "gradient", "light"] = "solid"
    accent_2: str = ""  # second gradient colour; empty derives one from the accent
    logo_url: str = Field(default="", max_length=512)
    corner: Literal["rounded", "soft", "square"] = "rounded"
    bubble: Literal["filled", "outline"] = "filled"
    size: Literal["standard", "large"] = "standard"
    font: Literal["system", "rounded", "serif", "mono"] = "system"

    @field_validator("accent")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not _HEX.match(v):
            raise ValueError("accent must be a #RRGGBB hex color")
        return v.upper()

    @field_validator("accent_2")
    @classmethod
    def _hex2(cls, v: str) -> str:
        v = v.strip()
        if v and not _HEX.match(v):
            raise ValueError("The second colour must be a #RRGGBB hex color")
        return v.upper()

    @field_validator("logo_url")
    @classmethod
    def _logo(cls, v: str) -> str:
        v = v.strip()
        if v and not v.startswith("https://"):
            raise ValueError("The logo URL must start with https://")
        return v

    @field_validator("suggestions")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        out = [s.strip()[:120] for s in v if s and s.strip()]
        return out[:4]


# Fields only paid plans (organization.custom_design) may change.
PRO_FIELDS = ("layout", "header_style", "accent_2", "logo_url", "corner", "bubble", "size", "font")


def without_custom_design(a: WidgetAppearance) -> WidgetAppearance:
    """The same appearance with the paid design options back at their defaults."""
    defaults = WidgetAppearance()
    return a.model_copy(update={f: getattr(defaults, f) for f in PRO_FIELDS})
