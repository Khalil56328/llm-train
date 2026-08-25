"""JWT 鉴权与权限控制"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer()


class SecurityService:
    """安全服务（供多处调用）"""

    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError:
            return None


# 保留原模块级函数以兼容已有代码
security_service = SecurityService()
hash_password = security_service.hash_password
verify_password = security_service.verify_password
create_access_token = security_service.create_access_token
decode_access_token = security_service.decode_access_token


# ========== 角色权限 ==========
# 角色 -> 权限码列表。"*" 表示拥有全部权限。
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "super_admin": ["*"],
    "admin": [
        "user:manage",   # 用户管理（创建/编辑/删除）
        "dict:manage",   # 字典管理
        "dataset:manage",
        "operator:manage",
        "model:manage",
        "train:manage",
        "deploy:manage",
        "eval:manage",
    ],
    "user": [
        "dataset:manage",
        "operator:manage",
        "model:manage",
        "train:manage",
        "deploy:manage",
        "eval:manage",
    ],
}


def get_role_permissions(role: str) -> List[str]:
    """根据角色返回权限码列表；角色不存在时按普通用户处理"""
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["user"])
    if "*" in perms:
        return ["*"]
    return list(perms)


def has_permission(role: str, permission: str) -> bool:
    """判断角色是否拥有某权限码"""
    perms = ROLE_PERMISSIONS.get(role, [])
    return "*" in perms or permission in perms


# ========== 角色校验依赖 ==========
def require_roles(*roles: str):
    """生成一个依赖，限制当前用户角色必须在 roles 中，否则返回 403。

    用法：
        @router.post("")
        async def create_x(data: dict, _user: dict = Depends(require_roles("super_admin", "admin"))):
            ...
    """

    async def _dependency(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无权执行该操作（需要角色: {'/'.join(roles)}）",
            )
        return user

    return _dependency


# ========== 当前用户依赖 ==========
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """从 Token 获取当前用户信息（从数据库验证）"""
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # 从数据库查询用户
    from app.models.user import User
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")

    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "role": user.role,
        "permissions": get_role_permissions(user.role),
    }

