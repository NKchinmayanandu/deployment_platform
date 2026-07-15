from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.deployment import Deployment,DeploymentStatus
    from app.models.user import User
    from app.models.environment_var import Environment