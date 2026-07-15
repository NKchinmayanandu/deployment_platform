from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.application import Application
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationOut
from app.models.environment_var import Environment
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
    await db.flush()
    for key,value in app_in.environment.items():
          db.add(
            Environment(
                application_id=application.id,
                key=key,
                value=value,
                )
            )  
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
    application = await check_app(app_id,db=db)
    return ApplicationOut.model_validate(application)
