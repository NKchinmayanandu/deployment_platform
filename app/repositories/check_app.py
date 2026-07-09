from fastapi import Depends,status,HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.application import Application
from app.db.session import get_db
async def check_app(app_id:int,db:AsyncSession):
    app = await db.execute(select(Application).where(Application.id==app_id))
    app = app.scalar_one_or_none()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Application not found or access denied"
        )
    return app
