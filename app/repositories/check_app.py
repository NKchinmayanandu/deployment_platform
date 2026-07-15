from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.application import Application
from sqlalchemy.orm import selectinload

async def check_app(app_id: int, db: AsyncSession):
    app = await db.execute(
        select(Application)
        .options(selectinload(Application.deployment))
        .where(Application.id == app_id)
    )
    return app.scalar_one_or_none()

