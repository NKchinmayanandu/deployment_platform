from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.deployment import Deployment
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Enum,
    ForeignKey,
    Integer,
    Text,
    DateTime,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class HealthCheck(Base):
    __tablename__ = "healthchecks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    status: Mapped[HealthStatus] = mapped_column(
        Enum(HealthStatus, name="healthstatus"),
        nullable=False,
        default=HealthStatus.UNKNOWN,
    )

    response_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    deployment: Mapped["Deployment"] = relationship(
        back_populates="health_checks"
    )
