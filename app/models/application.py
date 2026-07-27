from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.environment_var import Environment
from app.models.deployment import Deployment
class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), index=True)
    image_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="applications")
    deployment: Mapped["Deployment | None"] = relationship(
        back_populates="application", cascade="all, delete-orphan", uselist=False
    )
    environment_variables: Mapped[list["Environment"]] = relationship(
        "Environment", 
        back_populates="application",   
        cascade="all, delete-orphan"
    )
    container_port : Mapped[int] = mapped_column(default=8000)
