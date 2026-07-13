
from arq import cron 
from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.deployment_worker import (
    deploy_container_task,
    restart_container_task,
    start_container_task,
    remove_container_task,
    remove_deleted_container_task,
    stop_container_task,
)


def _redis_settings_from_url(url: str) -> RedisSettings:
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    functions = [
        deploy_container_task,
        stop_container_task,
        restart_container_task,
        start_container_task,
        remove_container_task,
        remove_deleted_container_task,
    ]

    redis_settings = _redis_settings_from_url(settings.REDIS_URL)

    max_jobs = 10
    job_timeout = 300       
    keep_result = 3600     
    max_tries = 3         
