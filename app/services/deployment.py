from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.get_deployment import deployment_get_app
from app.schemas.deployment import DeploymentStatusOut
async def get_deployment_status(app_id: int,
    db: AsyncSession,
    current_user: User):
    deployment = await deployment_get_app(app_id=app_id,
                                    db=db,
                                    current_user=current_user)
    if deployment is None:
        return {"message":"app is not deployed"}
    return DeploymentStatusOut.model_validate(deployment)