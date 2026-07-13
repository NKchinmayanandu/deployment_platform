"""
Deployment API routes.

Changes from the Celery version
--------------------------------
- Import `Request` from FastAPI to access `request.app.state.arq_pool`.
- Replace every `task.delay(...)` call with
      `await request.app.state.arq_pool.enqueue_job("function_name", ...)`
  `enqueue_job` is a coroutine — it must be awaited.
- The job name string must match the Python function name registered in
  WorkerSettings.functions (see app/workers/arq_worker.py).
- No other logic was changed.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.application import Application
from app.models.deployment import Deployment, DeploymentStatus
from app.models.user import User
from app.repositories.get_deployment import deployment_get_app
from app.repositories.update_status import update_db_status
from app.services.deployment import get_deployment_status

router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/{app_id}/deploy", status_code=status.HTTP_202_ACCEPTED)
async def deploy(
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.delete("/{app_id}")
async def remove(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}


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
