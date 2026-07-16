from datetime import datetime

from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    name: str
    image_name: str
    environment: dict[str,str] = {}
    container_port:int=8000


class ApplicationOut(BaseModel):
    id: int
    owner_id: int
    name: str
    image_name: str
    created_at: datetime

    model_config = {"from_attributes": True}
