from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.application import Application
from sqlalchemy.orm import selectinload
from app.models.user import User
from app.core.exceptions import NotFoundError,UnauthorizedError
async def check_app(app_id: int, db: AsyncSession):
    app = await db.execute(
        select(Application)
        .options(selectinload(Application.deployment))
        .where(Application.id == app_id)
    )
    return app.scalar_one_or_none()

async def get_application(app_id:int,db:AsyncSession,current_user:User):
    app = await db.execute(
        select(Application)
        .options(selectinload(Application.deployment))
        .where(Application.id == app_id)
    )
    if not app.scalar_one_or_none():
        raise NotFoundError(detail="application not found")

    if app.owner_id != current_user:
        raise UnauthorizedError(detail="u are not allowed")
    return app 