import uuid

from pydantic import BaseModel, Field


class OrganizationUsage(BaseModel):
    messages_used: int
    messages_limit: int
    bots_used: int
    bots_limit: int
    sources_limit: int
    members_limit: int
    shares_limit: int
    remove_branding: bool


class OrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    plan_name: str
    can_upgrade: bool
    allowed_model_tiers: list[str]
    role: str
    initial: str
    usage: OrganizationUsage


class OrganizationUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
