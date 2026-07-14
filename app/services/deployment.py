from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.get_deployment import deployment_get_app
from app.schemas.deployment import DeploymentStatusOut
from app.infrastructure.docker_client import client
from docker.errors import NotFound
async def get_deployment_status(app_id: int,
    db: AsyncSession,
    current_user: User):
    deployment = await deployment_get_app(app_id=app_id,
                                    db=db,
                                    current_user=current_user)
    return DeploymentStatusOut.model_validate(deployment)


def get_container_logs(deployment):
    try:
        container = client.containers.get(deployment.container_name)
        return container.logs(
            stdout=True,
            stderr=True,
            tail=300
        ).decode().splitlines()

    except NotFound:
        return ["Container does not exist."]