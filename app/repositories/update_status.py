from app.db.session import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.repositories.check_app import check_app
async def update_db_status(app_id:int,status:str,db:AsyncSession):
    app = await check_app(app_id=app_id,db=db)
    app.status = status
    await db.commit()
    await db.refresh(app)

    