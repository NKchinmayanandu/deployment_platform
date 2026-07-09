from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.application import Application
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationOut
from app.services.deployment_service import delete_application_container
from app.repositories.check_app import check_app
async def create_application(
    db: AsyncSession, app_in: ApplicationCreate, current_user: User
) -> ApplicationOut:
    
    application = Application(
        owner_id=current_user.id,
        name=app_in.name,
        image_name=app_in.image_name,
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return ApplicationOut.model_validate(application)


async def get_user_applications(
    db: AsyncSession, current_user: User
) -> list[ApplicationOut]:
    result = await db.execute(
        select(Application).where(Application.owner_id == current_user.id)
    )
    apps = result.scalars().all()
    return [ApplicationOut.model_validate(app) for app in apps]


async def get_application(
    db: AsyncSession, app_id: int, current_user: User
) -> ApplicationOut:
    application = await check_app(app_id)
    return ApplicationOut.model_validate(application)


async def delete_application(
    db: AsyncSession, app_id: int, current_user: User
) -> None:
    app = await check_app(app_id)
    deployment = app.deployment
    if current_user.id == app.owner_id:
        if app.deployment and deployment.container_name:
            await delete_application_container(app.deployment.container_name)
        else:
            raise HTTPException(status_code=400,detail="not allowed")
        await delete_application_container(app.deployment.container_name)
    await db.delete(app)
    await db.commit()



