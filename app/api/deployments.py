from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.post("/{app_id}/deploy")
async def deploy(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}


@router.post("/{app_id}/stop")
async def stop(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}


@router.post("/{app_id}/restart")
async def restart(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}


@router.delete("/{app_id}")
async def remove(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}


@router.get("/{app_id}")
async def status(app_id: int, current_user: User = Depends(get_current_user)):
    return {"detail": "Not implemented"}
