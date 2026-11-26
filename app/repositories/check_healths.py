from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.deployment import Deployment
from app.models.user import User
from app.models.health_checks import HealthCheck
from app.repositories.get_deployment import get_user_deployment

async def get_latest_health(deployment_id:int,current_user:User,db:AsyncSession):
    
    deployment = await get_user_deployment(
        deployment_id,
        current_user.id,
        db,
    )

    if deployment is None:
        raise HTTPException(
            status_code=404,
            detail="Deployment not found",
        )
    health_records = await (db.execute(select(HealthCheck).
                            where(HealthCheck.deployment_id==deployment_id).
                            order_by(HealthCheck.checked_at.desc()).limit(1)))
    health_records = health_records.scalar_one_or_none()
    return health_records