from app.workers.celery_app import celery_app


@celery_app.task(name="deploy_application")
def deploy_application_task(application_id: int) -> dict:
    # TODO: Implement Docker deployment logic
    return {"status": "not_implemented", "application_id": application_id}


@celery_app.task(name="stop_application")
def stop_application_task(application_id: int) -> dict:
    # TODO: Implement Docker stop logic
    return {"status": "not_implemented", "application_id": application_id}


@celery_app.task(name="restart_application")
def restart_application_task(application_id: int) -> dict:
    # TODO: Implement Docker restart logic
    return {"status": "not_implemented", "application_id": application_id}
