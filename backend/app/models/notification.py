"""系统通知模型"""
from sqlalchemy import Column, String, Boolean, DateTime, func
from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "系统通知表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    title = Column(String(200), nullable=False, comment="通知标题")
    content = Column(String(2000), comment="通知内容")
    level = Column(String(20), default="info", comment="级别: info/warning/error/success")
    is_read = Column(Boolean, default=False, comment="是否已读")
    user_id = Column(String(36), index=True, comment="接收用户ID（为空表示全体）")
    module = Column(String(50), comment="来源模块: training/deployment/evaluation/system")
    ref_id = Column(String(36), comment="关联业务ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
