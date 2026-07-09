from app.workers.celery_app import celery_app
import asyncio
from app.services.deployment_service import run_deployment_logic
from celery import Task
from app.repositories.update_status import update_db_status
from app.db.session import AsyncSessionLocal
@celery_app.task(bind=True,max_retries=3,default_retry_delay=60)
def deploy_container_task(self,deploymet_id:int,app_id:int,image_name:str):
    try:
        asyncio.run(_deploy(deployment_id=deploymet_id,app_id=app_id,image_name=image_name))
    except Exception as exc:
        raise self.retry(exc=exc)
    
async def _deploy(deployment_id:int,app_id,image_name):
    async with AsyncSessionLocal() as db:
        await update_db_status(app_id,status="deploying",db=db)
        await run_deployment_logic(deployment_id=deployment_id,image_name=image_name)
        await update_db_status(app_id,status="deployed",db=db)