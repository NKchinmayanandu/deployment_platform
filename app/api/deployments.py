from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.application import Application
from app.models.deployment import Deployment, DeploymentStatus
from app.models.user import User
from app.repositories.get_deployment import deployment_get_app,deployment_get
from app.repositories.update_status import update_db_status
from app.services.deployment import get_deployment_status,get_container_logs
import logging
import asyncio
router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/{app_id}/deploy", status_code=status.HTTP_202_ACCEPTED)
async def deploy(
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logging.info(f"deploy requested for app_id={app_id}")
    user = await db.execute(
        select(Application).where(
            Application.owner_id == current_user.id,
            Application.id == app_id,
        )
    )
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="application not found")

    image_name = user.image_name
    deployment = Deployment(
        application_id=app_id,
        status=DeploymentStatus.QUEUED,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    try:
        await request.app.state.arq_pool.enqueue_job(
            "deploy_container_task",
            deployment.id,
            image_name,
        )
    except Exception:
        logging.exception(Exception)
        raise HTTPException(
            status_code=503,
            detail="Unable to queue deployment task.",
        )

    return {"message": "deployment started"}


@router.post("/{app_id}/stop")
async def stop(
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deployment = await deployment_get_app(app_id=app_id, db=db, current_user=current_user)
    logging.info(f"stop deploy requested for deployment_id={deployment.id}")
    try:
        await request.app.state.arq_pool.enqueue_job(
            "stop_container_task",
            deployment_id=deployment.id,
            container_name=deployment.container_name,
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to queue deployment task.",
        )

    return {"message": "deployment is stopping"}


@router.post("/{app_id}/restart")
async def restart(
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deployment = await deployment_get_app(app_id=app_id, db=db, current_user=current_user)
    logging.info(f"restart deploy requested for deployment_id={deployment.id}")
    await update_db_status(deployment.id, DeploymentStatus.RESTARTING, db)

    try:
        await request.app.state.arq_pool.enqueue_job(
            "restart_container_task",
            deployment.id,
            deployment.container_name,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )

    return {"message": "deployment is getting restarted"}


@router.post("/{app_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start(
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deployment = await deployment_get_app(app_id=app_id, db=db, current_user=current_user)
    logging.info(f"start deploy requested for deployment_id={deployment.id}")
    await update_db_status(deployment.id, DeploymentStatus.STARTING, db)
    try:
        await request.app.state.arq_pool.enqueue_job(
            "start_container_task",
            deployment_id=deployment.id,
            container_name=deployment.container_name,
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to queue start task.",
        )
    return {"message": "deployment is starting"}


@router.delete("/{app_id}")
async def remove(
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deployment = await deployment_get_app(app_id=app_id, db=db, current_user=current_user)
    logging.info(f"remove deploy requested for deployment_id={deployment.id}")
    try:
        await request.app.state.arq_pool.enqueue_job(
            "remove_container_task",
            deployment_id=deployment.id,
            container_name=deployment.container_name,
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to queue remove task.",
        )
    return {"message": "deployment removal queued"}


@router.get("/{app_id}/status")
async def deployment_status(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_deployment_status(
        app_id=app_id,
        db=db,
        current_user=current_user,
    )
@router.get("/deployment/{deployment_id}/logs")
async def deployment_logs(
    deployment_id:int,
    db:AsyncSession=Depends(get_db)
):
    deployment = await deployment_get(depolyment_id=deployment_id,db=db)
    logging.info(f"deployment log for deployment_id:{deployment.id}")

    container_logs = await asyncio.to_thread(get_container_logs,deployment)

    return {"logs":container_logs}

    


