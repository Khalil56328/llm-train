"""字典数据模型"""
from sqlalchemy import Column, String, Integer, DateTime, func
from app.core.database import Base


class DictData(Base):
    __tablename__ = "dict_data"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "字典数据表"
    }

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键")
    dict_type = Column(String(50), nullable=False, index=True, comment="字典类型（映射前端枚举名）")
    dict_code = Column(String(50), nullable=False, comment="字典编码")
    dict_label = Column(String(100), nullable=False, comment="字典标签/显示值")
    dict_value = Column(String(100), comment="字典值")
    sort_order = Column(Integer, default=0, comment="排序")
    is_enabled = Column(String(1), default="1", comment="是否启用: 1=是 0=否")
    remark = Column(String(500), comment="备注")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
