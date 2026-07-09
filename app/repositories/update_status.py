from app.db.session import get_db
from app.models.application import Application
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
async def update_db_status(app_id:int,status:str,db:AsyncSession=Depends(get_db)):
    app = db.execute(select(Application).where(Application.id==app_id))
    app = app(
        status=status
    )
    db.add(app)
    await db.commit()
    await db.refresh()

    