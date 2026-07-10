from sqlalchemy.ext.asyncio import AsyncSession
from app.models.deployment import Deployment
from sqlalchemy import select
from app.models.user import User
async def deployment_get(depolyment_id:int,db:AsyncSession)->"Deployment|None":
    depolyment = await db.execute(select(Deployment).where(Deployment.id==depolyment_id))
    depolyment = depolyment.scalar_one_or_none()
    return depolyment

async def deployment_get_db(depolyment_id:int,db:AsyncSession,current_user:User)->"Deployment|None":
    depolyment = await db.execute(select(Deployment).where(User.id==current_user,
                                                           Deployment.id==depolyment_id))
    depolyment = depolyment.scalar_one_or_none()
    if not depolyment:
        return  {"detail":"you have not deployed"}
    return depolyment
