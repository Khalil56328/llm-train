"""用户模型"""
from sqlalchemy import Column, String, Boolean, DateTime, func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "用户表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    nickname = Column(String(100), comment="昵称")
    email = Column(String(100), comment="邮箱")
    role = Column(String(20), default="user", comment="角色: super_admin/admin/user")  # super_admin, admin, user
    department = Column(String(100), comment="部门")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
