from sqlalchemy.ext.asyncio import AsyncSession
from app.models.deployment import Deployment
from sqlalchemy import select
async def _get_deployment(depolyment_id:int,db:AsyncSession):
    depolyment = await db.execute(select(Deployment).where(Deployment.id==depolyment_id))
    depolyment = depolyment.scalar_one_or_none()
    return depolyment

