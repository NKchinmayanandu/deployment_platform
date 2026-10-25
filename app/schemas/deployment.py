from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field

from app.models.deployment import DeploymentStatus


class DeploymentOut(BaseModel):
    id: int
    application_id: int
    container_id: str | None
    container_name: str | None
    host_port: int | None
    status: DeploymentStatus
    deployment_url: str | None = None
    url: str | None = Field(default=None, validation_alias=AliasChoices("url", "deployment_url"))
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class DeploymentStatusOut(BaseModel):
    status: DeploymentStatus
    url: str | None = Field(default=None, validation_alias=AliasChoices("url", "deployment_url"))
    host_port: int | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


    