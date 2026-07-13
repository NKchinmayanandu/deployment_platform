from app.workers.celery_app import celery_app
import asyncio
from app.services.deployment_service import run_deployment_logic,stop_deployed_container
from celery import Task
from app.repositories.update_status import update_db_status
from app.db.session import AsyncSessionLocal
from app.models.deployment import DeploymentStatus
from app.services.deployment_service import restart_container
@celery_app.task(bind=True,max_retries=3,default_retry_delay=60)
def deploy_container_task(self,deployment_id:int,image_name:str):
    try:
        asyncio.run(_deploy(deployment_id=deployment_id,image_name=image_name))
    except Exception as exc:
        asyncio.run(_max_retry(deployment_id=deployment_id,status=DeploymentStatus.FAILED))
        raise self.retry(exc=exc)
@celery_app.task(bind=True,max_retries=3,default_retry_delay=60)
def stop_container_task(self,deployment_id,container_name):
    try:
        asyncio.run(_stop(deployment_id=deployment_id,container_name=container_name))
    except Exception as exc:
        asyncio.run(_max_retry(deployment_id=deployment_id,status=DeploymentStatus.FAILED))
        raise self.retry(exc=exc)
    

@celery_app.task(bind=True,max_retry=2,default_retry_delay=60)
def restart_container_task(self,deployment_id,container_name):
    try:
        asyncio.run(_restart(deployment_id=deployment_id,container_name=container_name))
    except Exception as exc:
        asyncio.run(_max_retry(deployment_id=deployment_id,status=DeploymentStatus.FAILED))
        raise self.retry(exc=exc)
    

async def _deploy(deployment_id:int,image_name):
    async with AsyncSessionLocal() as db:
        await update_db_status(deployment_id=deployment_id,status=DeploymentStatus.DEPLOYING,db=db)
        await run_deployment_logic(deployment_id=deployment_id,image_name=image_name)
        await update_db_status(deployment_id=deployment_id,status=DeploymentStatus.RUNNING,db=db)

async def _max_retry(deployment_id:int,status:str):
    async with AsyncSessionLocal() as db:
        await update_db_status(deployment_id=deployment_id,status=status,db=db)



async def _stop(deployment_id: int, container_name: str):
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
                db=db
            )
async def _restart(deployment_id:id,container_name):
    async with AsyncSessionLocal() as db:
        restart = await restart_container(container_name=container_name)

        if restart:
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.RUNNING,
                db=db
            )
        else:
            await update_db_status(
                deployment_id=deployment_id,
                status=DeploymentStatus.FAILED,
                db=db
            )
