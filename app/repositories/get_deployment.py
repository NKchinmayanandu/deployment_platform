from sqlalchemy.ext.asyncio import AsyncSession
from app.models.deployment import Deployment
from sqlalchemy import select
async def deployment_get(depolyment_id:int,db:AsyncSession)->"Deployment|None":
    depolyment = await db.execute(select(Deployment).where(Deployment.id==depolyment_id))
    depolyment = depolyment.scalar_one_or_none()
    return depolyment

