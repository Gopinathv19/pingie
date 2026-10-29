from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.mixins import TimestampCreated, TimestampUpdated, UUIDPrimaryKey


class Plan(UUIDPrimaryKey, TimestampCreated, TimestampUpdated, Base):
    """A subscription tier, managed from ping-admin. `Organization.plan` holds
    the key; limits are copied onto the org when the plan is applied."""

    __tablename__ = "plans"

    key: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    price_monthly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_label: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    messages_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    bots_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    sources_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    shares_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    members_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    remove_branding: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    model_tiers: Mapped[list] = mapped_column(JSONB, nullable=False, server_default='["fast"]')
    features: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    highlighted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
