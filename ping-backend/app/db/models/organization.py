import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.mixins import StatusColumn, TimestampCreated, UUIDPrimaryKey


class Organization(UUIDPrimaryKey, StatusColumn, TimestampCreated, Base):
    """The billing and ownership boundary. Bots belong to an organization."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, server_default="free")
    # Plan limits are copied onto the row so a plan change is one UPDATE and a
    # custom deal needs no code.
    messages_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    bots_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    sources_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    shares_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    members_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    remove_branding: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class OrganizationMember(UUIDPrimaryKey, TimestampCreated, Base):
    """Who may act inside an organization. Every query for a bot joins this."""

    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="owner")
