"""认证服务"""
from __future__ import annotations

import uuid
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.auth import SecurityService, get_role_permissions

security = SecurityService()


def _uuid() -> str:
    return uuid.uuid4().hex


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, username: str, password: str) -> Optional[Dict]:
        """用户登录验证"""
        result = await self.db.execute(
            select(User).where(
                User.username == username,
                User.is_active == True,
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        if not security.verify_password(password, user.password_hash):
            return None

        token = security.create_access_token({"sub": user.id, "username": user.username})
        return {
            "accessToken": token,
            "tokenType": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "email": user.email,
                "role": user.role,
                "department": user.department,
                "permissions": get_role_permissions(user.role),
            },
        }

    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        if not user:
            return None
        return _user_to_dict(user)

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        return _user_to_dict(user) if user else None

    async def list_users(
        self, *, page_index: int = 1, page_size: int = 20, keyword: Optional[str] = None
    ) -> Dict:
        from sqlalchemy import func
        q = select(User)
        count_q = select(func.count(User.id))
        if keyword:
            f = User.username.contains(keyword) | User.nickname.contains(keyword)
            q, count_q = q.where(f), count_q.where(f)
        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(User.created_at.desc())
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()
        return {
            "list": [_user_to_dict(u) for u in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def create_user(self, data: Dict) -> Dict:
        hashed = security.hash_password(data.get("password", "123456"))
        u = User(
            id=_uuid(),
            username=data["username"],
            password_hash=hashed,
            nickname=data.get("nickname", data["username"]),
            email=data.get("email"),
            role=data.get("role", "user"),
            department=data.get("department"),
            is_active=data.get("isActive", True),
        )
        self.db.add(u)
        await self.db.flush()
        await self.db.refresh(u)
        return _user_to_dict(u)

    async def update_user(self, user_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        u = result.scalar_one_or_none()
        if not u:
            return None
        for k, v in data.items():
            if v is not None and k != "password":
                setattr(u, k, v)
        if data.get("password"):
            u.password_hash = security.hash_password(data["password"])
        await self.db.flush()
        await self.db.refresh(u)
        return _user_to_dict(u)

    async def delete_user(self, user_id: str) -> bool:
        result = await self.db.execute(select(User).where(User.id == user_id))
        u = result.scalar_one_or_none()
        if not u:
            return False
        await self.db.delete(u)
        await self.db.flush()
        return True

    async def seed_admin_user(self) -> None:
        """初始化默认管理员"""
        result = await self.db.execute(
            select(User).where(User.username == "admin").limit(1)
        )
        if result.scalar_one_or_none():
            return
        u = User(
            id=_uuid(),
            username="admin",
            password_hash=security.hash_password("admin123"),
            nickname="超级管理员",
            email="admin@example.com",
            role="super_admin",
            department="技术中心",
            is_active=True,
        )
        self.db.add(u)
        await self.db.flush()


def _user_to_dict(u: User) -> Dict:
    return {
        "id": u.id,
        "username": u.username,
        "nickname": u.nickname,
        "email": u.email,
        "role": u.role,
        "department": u.department,
        "isActive": u.is_active,
        "permissions": get_role_permissions(u.role),
        "createdAt": u.created_at.isoformat() if u.created_at else None,
        "updatedAt": u.updated_at.isoformat() if u.updated_at else None,
    }
