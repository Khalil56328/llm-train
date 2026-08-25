"""用户/认证 Pydantic 模型"""
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class UserCreate(BaseModel):
    """创建用户请求体"""
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    nickname: Optional[str] = Field(None, max_length=64)
    email: Optional[str] = Field(None, max_length=128)
    role: str = Field("user", description="角色: super_admin/admin/user")
    department: Optional[str] = Field(None, max_length=128)
    isActive: bool = True

    @field_validator("role")
    @classmethod
    def check_role(cls, v: str) -> str:
        if v not in ("super_admin", "admin", "user"):
            raise ValueError("角色必须是 super_admin/admin/user 之一")
        return v


class UserUpdate(BaseModel):
    """更新用户请求体（字段均可选）"""
    nickname: Optional[str] = Field(None, max_length=64)
    email: Optional[str] = Field(None, max_length=128)
    password: Optional[str] = Field(None, min_length=6, max_length=128)
    role: Optional[str] = Field(None, description="角色: super_admin/admin/user")
    department: Optional[str] = Field(None, max_length=128)
    isActive: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def check_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("super_admin", "admin", "user"):
            raise ValueError("角色必须是 super_admin/admin/user 之一")
        return v


class UserOut(BaseModel):
    """用户响应体"""
    id: str
    username: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    role: str
    department: Optional[str] = None
    isActive: bool = True
    permissions: List[str] = []
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    class Config:
        from_attributes = True
