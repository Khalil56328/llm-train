"""算子中心 API"""
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.response import success_response
from app.services.operator_service import OperatorService
from app.schemas.operator import (
    OperatorCreate,
    OperatorUpdate,
    OperatorVersionCreate,
    OperatorVersionUpdate,
)

router = APIRouter()


# ========== 算子广场（静态路由需在动态路由前注册） ==========
@router.get("/plaza/search")
async def plaza_operators(
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(12, ge=1, le=100, alias="pageSize"),
    keyword: str = Query(None),
    category: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """算子广场：仅展示公开算子"""
    svc = OperatorService(db)
    result = await svc.list_operators(
        page_index=page_index, page_size=page_size,
        keyword=keyword, category=category, is_public=True,
    )
    return success_response(result)


# ========== 算子 CRUD ==========
@router.get("")
async def list_operators(
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    keyword: str = Query(None),
    category: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.list_operators(
        page_index=page_index, page_size=page_size,
        keyword=keyword, category=category,
    )
    return success_response(result)


@router.get("/{operator_id}")
async def get_operator(
    operator_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.get_operator(operator_id)
    if not result:
        raise HTTPException(status_code=404, detail="算子不存在")
    return success_response(result.model_dump())


@router.post("")
async def create_operator(
    payload: OperatorCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    owner_name = user.get("nickname") or user.get("username")
    result = await svc.create_operator(
        payload, owner=user["id"], owner_name=owner_name
    )
    return success_response(result.model_dump())


@router.put("/{operator_id}")
async def update_operator(
    operator_id: str,
    payload: OperatorUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.update_operator(operator_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="算子不存在")
    return success_response(result.model_dump())


@router.delete("/{operator_id}")
async def delete_operator(
    operator_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    ok = await svc.delete_operator(operator_id)
    if not ok:
        raise HTTPException(status_code=404, detail="算子不存在")
    return success_response({"message": "删除成功"})


# ========== 算子版本 CRUD ==========
@router.get("/{operator_id}/versions")
async def list_versions(
    operator_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.list_versions(operator_id)
    return success_response([r.model_dump() for r in result])


@router.get("/versions/{version_id}")
async def get_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.get_version(version_id)
    if not result:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response(result.model_dump())


@router.post("/{operator_id}/versions")
async def create_version(
    operator_id: str,
    payload: OperatorVersionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.create_version(operator_id, payload, creator=user["username"])
    if not result:
        raise HTTPException(status_code=404, detail="算子不存在")
    return success_response(result.model_dump())


@router.put("/versions/{version_id}")
async def update_version(
    version_id: str,
    payload: OperatorVersionUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.update_version(version_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response(result.model_dump())


@router.delete("/versions/{version_id}")
async def delete_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    ok = await svc.delete_version(version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response({"message": "删除成功"})


# 兼容前端调用：/operators/{operator_id}/versions/{version_id}
@router.put("/{operator_id}/versions/{version_id}")
async def update_version_nested(
    operator_id: str,
    version_id: str,
    payload: OperatorVersionUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    # 校验版本确实属于该算子
    ver = await svc.get_version(version_id)
    if not ver or ver.operator_id != operator_id:
        raise HTTPException(status_code=404, detail="版本不存在")
    result = await svc.update_version(version_id, payload)
    return success_response(result.model_dump())


@router.delete("/{operator_id}/versions/{version_id}")
async def delete_version_nested(
    operator_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    ver = await svc.get_version(version_id)
    if not ver or ver.operator_id != operator_id:
        raise HTTPException(status_code=404, detail="版本不存在")
    ok = await svc.delete_version(version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response({"message": "删除成功"})


# ========== 镜像 ==========
@router.get("/images/search")
async def search_images(
    page_index: int = Query(1, alias="pageIndex"),
    page_size: int = Query(10, alias="pageSize"),
    keyword: str = Query(None),
    resource_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.list_images(
        page_index=page_index,
        page_size=page_size,
        keyword=keyword,
        resource_type=resource_type,
    )
    return success_response(result)


# 前端镜像选择弹框调用的是 /images/list（已迁移至运维中心，此处兼容保留）
@router.get("/images/list")
async def list_images(
    page_index: int = Query(1, alias="pageIndex"),
    page_size: int = Query(10, alias="pageSize"),
    keyword: str = Query(None),
    resource_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = OperatorService(db)
    result = await svc.list_images(
        page_index=page_index,
        page_size=page_size,
        keyword=keyword,
        resource_type=resource_type,
    )
    return success_response(result)
