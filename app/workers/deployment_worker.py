from app.db.session import AsyncSessionLocal
from app.models.deployment import DeploymentStatus
from app.repositories.update_status import update_db_status
from app.services.deployment_service import (
    restart_container,
    run_deployment_logic,
    stop_deployed_container,
)


async def _deploy(deployment_id: int, image_name: str) -> None:
    async with AsyncSessionLocal() as db:
        await update_db_status(deployment_id=deployment_id, status=DeploymentStatus.DEPLOYING, db=db)
        await run_deployment_logic(deployment_id=deployment_id, image_name=image_name)
        await update_db_status(deployment_id=deployment_id, status=DeploymentStatus.RUNNING, db=db)


async def _stop(deployment_id: int, container_name: str) -> None:
    async with AsyncSessionLocal() as db:
        stopped = await stop_deployed_container(container_name)
        if stopped:
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.STOPPED,
                db=db,
            )
        else:
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                db=db,
            )


async def _restart(deployment_id: int, container_name: str) -> None:
    async with AsyncSessionLocal() as db:
        restarted = await restart_container(container_name=container_name)
        if restarted:
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.RUNNING,
                db=db,
            )
        else:
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                db=db,
            )


async def _mark_failed(deployment_id: int) -> None:
    async with AsyncSessionLocal() as db:
        await update_db_status(deployment_id=deployment_id, status=DeploymentStatus.FAILED, db=db)


async def deploy_container_task(ctx: dict, deployment_id: int, image_name: str) -> None:
    try:
        await _deploy(deployment_id=deployment_id, image_name=image_name)
    except Exception:
        await _mark_failed(deployment_id=deployment_id)
        raise  


async def stop_container_task(ctx: dict, deployment_id: int, container_name: str) -> None:
    try:
        await _stop(deployment_id=deployment_id, container_name=container_name)
    except Exception:
        await _mark_failed(deployment_id=deployment_id)
        raise


async def restart_container_task(ctx: dict, deployment_id: int, container_name: str) -> None:
    try:
        await _restart(deployment_id=deployment_id, container_name=container_name)
    except Exception:
        await _mark_failed(deployment_id=deployment_id)
        raise
