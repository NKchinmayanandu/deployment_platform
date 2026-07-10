from app.workers.celery_app import celery_app
import asyncio
from app.services.deployment_service import run_deployment_logic
from celery import Task
from app.repositories.update_status import update_db_status
from app.db.session import AsyncSessionLocal
from app.models.deployment import DeploymentStatus
@celery_app.task(bind=True,max_retries=3,default_retry_delay=60)
def deploy_container_task(self,deployment_id:int,image_name:str):
    try:
        print("Task started")
        asyncio.run(_deploy(deployment_id=deployment_id,image_name=image_name))
    except Exception as exc:
        print(exc)
        raise
    """
    except Exception as exc:
        asyncio.run(_max_retry(deployment_id=deployment_id,status=DeploymentStatus.FAILED))
        raise self.retry(exc=exc)
    """
    
async def _deploy(deployment_id:int,image_name):
    async with AsyncSessionLocal() as db:
        await update_db_status(deployment_id=deployment_id,status=DeploymentStatus.DEPLOYING,db=db)
        await run_deployment_logic(deployment_id=deployment_id,image_name=image_name)
        await update_db_status(deployment_id=deployment_id,status=DeploymentStatus.RUNNING,db=db)

async def _max_retry(deployment_id:int,status:str):
    async with AsyncSessionLocal() as db:
        await update_db_status(deployment_id=deployment_id,status=status,db=db)