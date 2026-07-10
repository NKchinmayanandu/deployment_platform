from app.db.session import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.get_deployment import deployment_get
async def update_db_status(deployment_id:int,status:str,db:AsyncSession):
    app = await deployment_get(depolyment_id=deployment_id,db=db)
    app.status = status
    await db.commit()
    await db.refresh(app)

    