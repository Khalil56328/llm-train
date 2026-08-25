"""系统通知服务"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now()


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_notifications(
        self,
        *,
        page_index: int = 1,
        page_size: int = 20,
        user_id: Optional[str] = None,
        is_read: Optional[bool] = None,
        level: Optional[str] = None,
    ) -> Dict:
        q = select(Notification)
        count_q = select(func.count(Notification.id))

        # 筛选：指定用户 或 全体通知
        if user_id:
            f = (Notification.user_id == user_id) | (Notification.user_id.is_(None)) | (Notification.user_id == "")
            q, count_q = q.where(f), count_q.where(f)
        if is_read is not None:
            q, count_q = q.where(Notification.is_read == is_read), count_q.where(Notification.is_read == is_read)
        if level:
            q, count_q = q.where(Notification.level == level), count_q.where(Notification.level == level)

        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(Notification.created_at.desc())
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()

        return {
            "list": [_notify_to_dict(n) for n in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def create_notification(
        self, *,
        title: str,
        content: Optional[str] = None,
        level: str = "info",
        user_id: Optional[str] = None,
        module: Optional[str] = None,
        ref_id: Optional[str] = None,
    ) -> Dict:
        n = Notification(
            id=_uuid(),
            title=title,
            content=content,
            level=level,
            is_read=False,
            user_id=user_id,
            module=module,
            ref_id=ref_id,
        )
        self.db.add(n)
        await self.db.flush()
        await self.db.refresh(n)
        return _notify_to_dict(n)

    async def mark_as_read(self, notification_id: str) -> bool:
        result = await self.db.execute(
            update(Notification).where(Notification.id == notification_id)
            .values(is_read=True)
        )
        await self.db.flush()
        return result.rowcount > 0

    async def mark_all_read(self, user_id: Optional[str] = None) -> int:
        q = update(Notification).values(is_read=True)
        if user_id:
            q = q.where(
                (Notification.user_id == user_id) |
                (Notification.user_id.is_(None)) |
                (Notification.user_id == "")
            )
        result = await self.db.execute(q)
        await self.db.flush()
        return result.rowcount

    async def get_unread_count(self, user_id: Optional[str] = None) -> int:
        q = select(func.count(Notification.id)).where(Notification.is_read == False)
        if user_id:
            q = q.where(
                (Notification.user_id == user_id) |
                (Notification.user_id.is_(None)) |
                (Notification.user_id == "")
            )
        result = await self.db.execute(q)
        return result.scalar() or 0

    async def delete_notification(self, notification_id: str) -> bool:
        result = await self.db.execute(select(Notification).where(Notification.id == notification_id))
        n = result.scalar_one_or_none()
        if not n:
            return False
        await self.db.delete(n)
        await self.db.flush()
        return True


def _notify_to_dict(n: Notification) -> Dict:
    return {
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "level": n.level,
        "isRead": n.is_read,
        "userId": n.user_id,
        "module": n.module,
        "refId": n.ref_id,
        "createdAt": n.created_at.isoformat() if n.created_at else None,
    }
