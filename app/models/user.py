from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from app.db.base import Base
from datetime import datetime

class Endpoint(Base):
    __tablename__ = "endpoints"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"),index=True)
    last_status = Column(String, nullable=True)
    last_checked = Column(DateTime, nullable=True)
    last_changed = Column(DateTime, nullable=True)