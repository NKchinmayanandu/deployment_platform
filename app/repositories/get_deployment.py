from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.deployment import Deployment
from sqlalchemy import select,join
from app.models.user import User
from app.models.application import Application
async def deployment_get(deployment_id:int,db:AsyncSession)->"Deployment|None":
    depolyment = await db.execute(select(Deployment).where(Deployment.id==deployment_id))
    depolyment = depolyment.scalar_one_or_none()
    return depolyment


async def deployment_get_app(app_id: int, db: AsyncSession, current_user: User):
    app_check = await db.execute(
        select(Application)
        .where(Application.id == app_id, Application.owner_id == current_user.id)
    )
    if not app_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found or access denied")

    result = await db.execute(
        select(Deployment)
        .where(
            Deployment.application_id == app_id
        )
    )
    
    deployment = result.scalar_one_or_none()
    
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="you have not deployed")
        
    return deployment