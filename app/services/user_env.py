from app.schemas.env import EnvironmentUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.repositories.get_env import env_get
from app.models.environment_var import Environment
import logging
async def update_user_env(
    env : EnvironmentUpdate,
    app_id:int,
    db:AsyncSession,
    current_user:User
    ):
    new_env = env.variables
    old_env_rows = await env_get(app_id=app_id,db=db)
    old_env = {row.key:row for row in old_env_rows}

    for key,value in new_env.items():
        if key in old_env:
            old_env[key].value = value
        else:
            db.add(
                Environment(
                    application_id=app_id,
                    key = key,
                    value = value
                )
            )
    for key, env in old_env.items():

        if key not in new_env:
            await db.delete(env)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logging.exception(f"could not able to commit to db : {e}")
        return False
    return True