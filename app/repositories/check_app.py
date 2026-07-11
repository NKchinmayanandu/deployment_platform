from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.application import Application
async def check_app(app_id:int,db:AsyncSession):
    app = await db.execute(select(Application).where(Application.id==app_id))
    app = app.scalar_one_or_none()
    return app
