from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.health_checks import HealthStatus


class HealthCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deployment_id: int
    status: HealthStatus
    response_time_ms: int | None
    error_message: str | None
    checked_at: datetime


class HealthCheckSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: HealthStatus
    response_time_ms: int | None
    error_message: str | None
    checked_at: datetime | None
