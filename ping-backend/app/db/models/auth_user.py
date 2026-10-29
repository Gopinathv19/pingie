import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.mixins import StatusColumn, TimestampCreated, UUIDPrimaryKey


class AuthenticatedUser(UUIDPrimaryKey, TimestampCreated, StatusColumn, Base):
    """One external identity (today only Google) linked to a user."""

    __tablename__ = "authenticated_user"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_auth_provider"),
        UniqueConstraint("user_id", "provider", name="uq_auth_user_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
