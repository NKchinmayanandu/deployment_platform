from fastapi import APIRouter, Depends,status,HTTPException
from sqlalchemy import select
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.models.user import User
from app.workers.deployment_worker import deploy_container_task
from app.models.application import Application
from app.models.deployment import Deployment,DeploymentStatus
from app.repositories.get_deployment import deployment_get_db
from app.schemas.deployment import DeploymentStatusOut
router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/{app_id}/deploy",status_code=status.HTTP_202_ACCEPTED)
async def deploy(app_id: int,
                 db : AsyncSession=Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    user = await db.execute(select(Application).where(Application.owner_id==current_user.id,
                                                      Application.id==app_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404,detail="application not found")
    image_name = user.image_name
    deployment = Deployment(
        application_id=app_id,
        status = DeploymentStatus.QUEUED
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    deploy_container_task.delay(deployment.id,image_name)
    return {
        "message":"deployment started"
    }


@router.post("/{app_id}/stop")
async def stop(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}


@router.post("/{app_id}/restart")
async def restart(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}


@router.delete("/{app_id}")
async def remove(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}


@router.get("/{app_id}/status")
async def status(deployment_id: int,db:AsyncSession=Depends(get_db),current_user: User = Depends(get_current_user)):
    deployment = await deployment_get_db(depolyment_id=deployment_id,db=db,current_user=current_user)
    return DeploymentStatusOut.model_validate(deployment)

