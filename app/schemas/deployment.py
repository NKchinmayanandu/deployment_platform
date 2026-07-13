from datetime import datetime

from pydantic import BaseModel

from app.models.deployment import DeploymentStatus


class DeploymentOut(BaseModel):
    id: int
    application_id: int
    container_id: str | None
    container_name: str | None
    host_port: int | None
    status: DeploymentStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeploymentStatusOut(BaseModel):
    status: DeploymentStatus
    url: str | None = None
    host_port: int | None = None

    model_config = {"from_attributes":True}


    