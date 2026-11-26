from fastapi import APIRouter, Depends, HTTPException, status 
from app.db.session import get_db
from app.schemas.health_checks import HealthCheckSummary,HealthCheckResponse
from app.api.dependencies import get_current_user
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.check_healths import get_latest_health
router = APIRouter(prefix="/deployments",tags=["Health Checks"])

@router.get("/{deployment_id}/health")
async def get_latest_health(
    deployment_id : int,
    current_user : User = Depends(get_current_user),
    db : AsyncSession = Depends(get_db)
):
    health_record = await get_latest_health(deployment_id=deployment_id,
                                            current_user=current_user,
                                            db=db)
    if health_record is None:
        raise HTTPException(status_code=404,detail="Health record do not exists")
    return HealthCheckSummary.model_validate(health_record)