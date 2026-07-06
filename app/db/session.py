import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL,pool_pre_ping=True,
                       pool_size=5,
                       max_overflow=10,
                       pool_timeout=30)

SessionLocal = sessionmaker(bind=engine)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()