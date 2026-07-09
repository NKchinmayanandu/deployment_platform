from fastapi import APIRouter, Depends,status,HTTPException
from sqlalchemy import select
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.models.user import User
from app.workers.deployment_worker import deploy_container_task
from app.models.application import Application
from app.repositories.check_app import check_app
from app.models.deployment import Deployment
router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/{app_id}/deploy",status_code=status.HTTP_202_ACCEPTED)
async def deploy(app_id: int,
                 db : AsyncSession=Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    user = db.execute(Application).where(Application.owner_id==current_user.id)
    if not user:
        raise HTTPException(status_code=404,detail="Not allowed")
    app = await check_app(app_id=app_id,db=db,image_name=image_name)
    image_name = app.image_name
    deployment = Deployment(
        application_id=app_id,
        status = "Queued"
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    deploy_container_task.delay(deployment.id,app_id)
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


@router.get("/{app_id}")
async def status(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}
