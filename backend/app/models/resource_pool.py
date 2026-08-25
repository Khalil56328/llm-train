"""计算资源池模型（运维中心）"""
from sqlalchemy import Column, String, Integer, DateTime

from app.core.database import Base


class ResourcePool(Base):
    __tablename__ = "resource_pools"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "计算资源池表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    name = Column(String(100), unique=True, nullable=False, comment="资源池名称")
    gpu_type = Column(String(50), default="A100", comment="GPU 类型：A100/V100/H800/A10 等")
    node_count = Column(Integer, default=1, comment="节点数")
    total_gpu = Column(Integer, default=0, comment="GPU 总数")
    available_gpu = Column(Integer, default=0, comment="可用 GPU 数")
    status = Column(String(20), default="active", comment="状态：active/inactive")
    description = Column(String(500), comment="资源池描述")
    created_at = Column(DateTime, comment="创建时间")
    updated_at = Column(DateTime, comment="更新时间")
