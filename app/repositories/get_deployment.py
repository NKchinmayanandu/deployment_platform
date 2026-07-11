from sqlalchemy.ext.asyncio import AsyncSession
from app.models.deployment import Deployment
from sqlalchemy import select,join
from app.models.user import User
from app.models.application import Application
async def deployment_get(depolyment_id:int,db:AsyncSession)->"Deployment|None":
    depolyment = await db.execute(select(Deployment).where(Deployment.id==depolyment_id))
    depolyment = depolyment.scalar_one_or_none()
    return depolyment


async def deployment_get_app(app_id: int, db: AsyncSession, current_user: User):
    app_check = await db.execute(
        select(Application)
        .where(Application.id == app_id, Application.owner_id == current_user.id)
    )
    if not app_check.scalar_one_or_none():
        return {"detail": "Application not found or access denied"}

    result = await db.execute(
        select(Deployment)
        .where(
            Deployment.application_id == app_id
        )
    )
    
    deployment = result.scalar_one_or_none()
    
    if not deployment:
        return {"detail": "you have not deployed"}
        
    return deployment