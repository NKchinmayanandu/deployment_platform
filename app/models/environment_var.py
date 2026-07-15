from typing import TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
if TYPE_CHECKING:
    from app.models.application import Application
from app.db.base import Base
from sqlalchemy import ForeignKey,UniqueConstraint

class Environment(Base):
    __tablename__ = "environments"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE")
    )
    key: Mapped[str]
    value: Mapped[str]
    application: Mapped["Application"] = relationship(
        back_populates="environment_variables"
    )
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "key",
            name="uq_environment_key_per_application",
        ),
    )
    