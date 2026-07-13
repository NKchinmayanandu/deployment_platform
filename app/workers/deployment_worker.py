from app.db.session import AsyncSessionLocal
from app.models.deployment import DeploymentStatus
from app.repositories.update_status import update_db_status
from app.services.deployment_service import (
    restart_container,
    run_deployment_logic,
    start_container,
    remove_container,
    stop_deployed_container,
)
import logging


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
    logging.info("deploy container started")
    try:
        await _deploy(deployment_id=deployment_id, image_name=image_name)
    except Exception:
        await _mark_failed(deployment_id=deployment_id)
        logging.exception(f"deploy container failed")
        raise  


async def stop_container_task(ctx: dict, deployment_id: int, container_name: str) -> None:
    logging.info("stop container started")
    try:
        await _stop(deployment_id=deployment_id, container_name=container_name)
    except Exception:
        await _mark_failed(deployment_id=deployment_id)
        logging.exception(f"stop container failed")
        raise


async def restart_container_task(ctx: dict, deployment_id: int, container_name: str) -> None:
    logging.info("restart container started")
    try:
        await _restart(deployment_id=deployment_id, container_name=container_name)
    except Exception:
        await _mark_failed(deployment_id=deployment_id)
        logging.exception(f"restart container failed")
        raise


async def _start(deployment_id: int, container_name: str) -> None:
    async with AsyncSessionLocal() as db:
        ok, reason = await start_container(container_name)

        if reason == "already_running":
            logging.info(f"Container {container_name} already running, skipping start.")
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.RUNNING,
                db=db,
            )
        elif ok:  # reason == "started"
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.RUNNING,
                db=db,
            )
        else:  # not_found
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                db=db,
            )


async def _remove(deployment_id: int, container_name: str) -> None:
    async with AsyncSessionLocal() as db:
        _ok, reason = await remove_container(container_name)
        if reason in ("removed", "not_found"):
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.REMOVED,
                db=db,
            )


async def start_container_task(ctx: dict, deployment_id: int, container_name: str) -> None:
    logging.info(f"start container task for deployment_id={deployment_id}")
    try:
        await _start(deployment_id=deployment_id, container_name=container_name)
    except Exception:
        await _mark_failed(deployment_id=deployment_id)
        logging.exception("start container task failed")
        raise


async def remove_container_task(ctx: dict, deployment_id: int, container_name: str) -> None:
    logging.info(f"remove container task for deployment_id={deployment_id}")
    try:
        await _remove(deployment_id=deployment_id, container_name=container_name)
    except Exception:
        await _mark_failed(deployment_id=deployment_id)
        logging.exception("remove container task failed")
        raise
