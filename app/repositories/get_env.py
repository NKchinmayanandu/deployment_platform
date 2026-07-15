from sqlalchemy.ext.asyncio import AsyncSession
from app.models.environment_var import Environment
from sqlalchemy import select
async def env_get(app_id:int,db:AsyncSession):

    result = await db.execute(
        select(Environment).where(
            Environment.application_id == app_id
        )
    )
    env_rows = result.scalars().all()
    return env_rows
