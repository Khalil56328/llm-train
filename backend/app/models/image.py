"""Docker 镜像资源模型（运维中心）"""
from sqlalchemy import Column, String, DateTime, func

from app.core.database import Base


class DockerImage(Base):
    __tablename__ = "docker_images"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "Docker 基础镜像表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    name = Column(String(100), unique=True, nullable=False, comment="镜像名称")
    address = Column(String(500), nullable=False, comment="镜像完整地址")
    resource_type = Column(String(20), default="CPU", comment="资源类型：CPU/GPU")
    description = Column(String(500), comment="镜像描述")
    created_at = Column(DateTime, comment="创建时间")
    updated_at = Column(DateTime, comment="更新时间")
