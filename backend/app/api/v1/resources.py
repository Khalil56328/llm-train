"""计算资源池管理 API（运维中心）"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.database import get_db
from app.core.response import success_response
from app.services.resource_service import ResourcePoolService
from app.schemas.resource_pool import ResourcePoolCreate, ResourcePoolUpdate

router = APIRouter()


@router.get("")
async def list_resource_pools(
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(10, ge=1, le=9999, alias="pageSize"),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """资源池分页查询（所有登录用户可读）"""
    svc = ResourcePoolService(db)
    result = await svc.list_pools(
        page_index=page_index,
        page_size=page_size,
        keyword=keyword,
        status=status,
    )
    return success_response(result)


@router.get("/{pool_id}")
async def get_resource_pool(
    pool_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """资源池详情"""
    svc = ResourcePoolService(db)
    result = await svc.get_pool(pool_id)
    if not result:
        raise HTTPException(status_code=404, detail="资源池不存在")
    return success_response(result.model_dump())


@router.post("")
async def create_resource_pool(
    payload: ResourcePoolCreate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_roles("super_admin", "admin")),
):
    """新增资源池（管理角色）"""
    svc = ResourcePoolService(db)
    result = await svc.create_pool(payload)
    return success_response(result.model_dump())


@router.put("/{pool_id}")
async def update_resource_pool(
    pool_id: str,
    payload: ResourcePoolUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_roles("super_admin", "admin")),
):
    """更新资源池（管理角色）"""
    svc = ResourcePoolService(db)
    result = await svc.update_pool(pool_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="资源池不存在")
    return success_response(result.model_dump())


@router.delete("/{pool_id}")
async def delete_resource_pool(
    pool_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_roles("super_admin", "admin")),
):
    """删除资源池（管理角色）"""
    svc = ResourcePoolService(db)
    deleted = await svc.delete_pool(pool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="资源池不存在")
    return success_response({"id": pool_id, "message": "删除成功"})
