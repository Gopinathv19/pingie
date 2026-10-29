import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKey:
    """Server-side UUID primary key (`gen_random_uuid()`, built into Neon), with
    a Python-side default so objects have an id before flush."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )


class TimestampCreated:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TimestampUpdated:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StatusColumn:
    """Lifecycle status as VARCHAR, not a PostgreSQL ENUM: a new status is an
    application change, not a migration. Allowed values live in the schemas."""

    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
