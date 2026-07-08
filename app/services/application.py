from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.application import Application
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationOut
from app.services.deployment_service import delete_application_container
from sqlalchemy.orm import selectinload     
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
    application = await _get_owned_application(db, app_id, current_user)
    return ApplicationOut.model_validate(application)


async def delete_application(
    db: AsyncSession, app_id: int, current_user: User
) -> None:
    app = await _get_owned_application(db, app_id, current_user)
    deployment = app.deployment
    if app.deployment and deployment.container_name:
        await delete_application_container(app.deployment.container_name)
    await db.delete(app)
    await db.commit()


async def _get_owned_application(   
    db: AsyncSession, app_id: int, current_user: User
) -> Application:
    result = await db.execute(
        select(Application).
        options(selectinload(Application.deployment)).
        where(Application.id == app_id))
    application = result.scalar_one_or_none()

    if not application:
        raise NotFoundError("Application not found")
    if application.owner_id != current_user.id:
        raise ForbiddenError("You don't own this application")

    return application
