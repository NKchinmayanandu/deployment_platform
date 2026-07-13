from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.application import ApplicationCreate, ApplicationOut
from app.services.application import (
    create_application,
    get_application,
    get_user_applications,
)
from app.repositories.check_app import check_app
import logging
router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post("/", response_model=ApplicationOut, status_code=201)
async def create(
    app_in: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logging.info("create app requested")
    return await create_application(db, app_in, current_user)


@router.get("/", response_model=list[ApplicationOut])
async def list_applications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logging.info("get app list requested")
    return await get_user_applications(db, current_user)


@router.get("/{app_id}", response_model=ApplicationOut)
async def get(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logging.info("get app requested")
    return await get_application(db, app_id, current_user)


from fastapi import HTTPException, Request

@router.delete("/{app_id}", status_code=204)
async def delete(
    app_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logging.info("delete app requested")
    app = await check_app(app_id, db=db)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if app.deployment and app.deployment.container_name:
        await request.app.state.arq_pool.enqueue_job(
            "remove_deleted_container_task",
            app.deployment.container_name,
        )
    
    await db.delete(app)
    await db.commit()
