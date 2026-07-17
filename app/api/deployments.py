from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.application import Application
from app.models.deployment import Deployment, DeploymentStatus
from app.models.user import User
from app.repositories.get_deployment import deployment_get_app,deployment_get_app_none
from app.repositories.update_status import update_db_status
from app.services.deployment import get_deployment_status,get_container_logs
import logging
import asyncio
from app.repositories.get_env import env_get
from app.repositories.check_app import get_app
router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/{app_id}/deploy", status_code=status.HTTP_202_ACCEPTED)
async def deploy(
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logging.info(f"deploy requested for app_id={app_id}")
    app = await get_app(app_id=app_id,db=db,current_user=current_user)
    logging.info("got the application")
    deployment = await deployment_get_app_none(app_id=app_id,db=db,current_user=current_user)
    if deployment is None:
        logging.info("deployment not found")
        deployment = Deployment(
        application_id=app_id,
        status=DeploymentStatus.QUEUED,
        )
        db.add(deployment)
        await db.commit()
        await db.refresh(deployment)
    else:
        deployment.status = DeploymentStatus.QUEUED
        deployment.container_id = None
        deployment.container_name = None
        deployment.host_port = None
        deployment.deployment_url = None
    await db.commit()
    await db.refresh(deployment) 
    logging.info("commited to the db")  
    image_name = app.image_name
    container_port = app.container_port
    env = await env_get(app_id=app_id,db=db)
    env = {row.key:row.value for row in env}
    logging.info("About to enqueue deploy")
    try:
        job = await request.app.state.arq_pool.enqueue_job(
            "deploy_container_task",
            deployment.id,
            image_name,
            env,
            container_port
        )
        logging.info(f"Deploy job: {job}")
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
    await update_db_status(deployment_id=deployment.id,status=DeploymentStatus.STARTING,db=db)
    try:
        job = await request.app.state.arq_pool.enqueue_job(
            "start_container_task",
            deployment_id=deployment.id,
            container_name=deployment.container_name,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(e)
        raise
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
@router.get("/{app_id}/logs")
async def deployment_logs(
    app_id:int,
    db:AsyncSession=Depends(get_db),
    current_user:User=Depends(get_current_user)
):
    deployment = await deployment_get_app(app_id=app_id, db=db, current_user=current_user)
    logging.info(f"deployment log for deployment_id:{deployment.id}")

    container_logs = await asyncio.to_thread(get_container_logs,deployment)

    return {"logs":container_logs}

    


