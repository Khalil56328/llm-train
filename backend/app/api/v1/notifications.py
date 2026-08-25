"""通知消息接口"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.response import success_response
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("")
async def get_notifications(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    level: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """获取通知列表"""
    svc = NotificationService(db)
    result = await svc.list_notifications(
        page_index=page_index, page_size=page_size,
        user_id=user["id"], level=level,
    )
    return success_response(result)


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = NotificationService(db)
    count = await svc.get_unread_count(user_id=user["id"])
    return success_response({"count": count})


@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = NotificationService(db)
    ok = await svc.mark_as_read(notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在")
    return success_response({"message": "已标记为已读"})


@router.put("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = NotificationService(db)
    count = await svc.mark_all_read(user_id=user["id"])
    return success_response({"message": f"已标记 {count} 条通知为已读"})


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = NotificationService(db)
    ok = await svc.delete_notification(notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在")
    return success_response({"message": "删除成功"})
