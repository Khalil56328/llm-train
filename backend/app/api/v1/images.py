"""镜像资源管理 API（运维中心）"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.core.response import success_response
from app.services.image_service import ImageService
from app.schemas.image import ImageCreate, ImageUpdate

router = APIRouter()


@router.get("")
async def list_images(
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
    keyword: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """镜像分页查询（所有登录用户可读）"""
    svc = ImageService(db)
    result = await svc.list_images(
        page_index=page_index,
        page_size=page_size,
        keyword=keyword,
        resource_type=resource_type,
    )
    return success_response(result)


@router.get("/{image_id}")
async def get_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """镜像详情"""
    svc = ImageService(db)
    result = await svc.get_image(image_id)
    if not result:
        raise HTTPException(status_code=404, detail="镜像不存在")
    return success_response(result.model_dump())


@router.post("")
async def create_image(
    payload: ImageCreate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_roles("super_admin", "admin")),
):
    """新增镜像（管理角色）"""
    svc = ImageService(db)
    result = await svc.create_image(payload)
    return success_response(result.model_dump())


@router.put("/{image_id}")
async def update_image(
    image_id: str,
    payload: ImageUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_roles("super_admin", "admin")),
):
    """更新镜像（管理角色）"""
    svc = ImageService(db)
    result = await svc.update_image(image_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="镜像不存在")
    return success_response(result.model_dump())


@router.delete("/{image_id}")
async def delete_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_roles("super_admin", "admin")),
):
    """删除镜像（管理角色）"""
    svc = ImageService(db)
    deleted = await svc.delete_image(image_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="镜像不存在")
    return success_response({"id": image_id, "message": "删除成功"})
