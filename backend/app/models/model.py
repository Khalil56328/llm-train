"""模型库模型"""
from sqlalchemy import Column, String, Boolean, DateTime, BigInteger, Integer, ForeignKey, func
from app.core.database import Base


class Model(Base):
    __tablename__ = "models"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "模型库主表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    name = Column(String(200), nullable=False, comment="模型名称")
    type = Column(String(50), comment="类型")            # dialogue, vision, image-generation, embedding, rerank...
    spec = Column(String(20), comment="规格")            # below-10b, 10b-50b, 50b-100b, above-100b
    vendor = Column(String(100), comment="厂商/来源")
    version = Column(String(20), comment="当前版本")
    description = Column(String(500), comment="描述")
    tags = Column(String(500), comment="标签JSON")           # JSON array
    icon_url = Column(String(500), comment="图标URL")
    storage_path = Column(String(500), comment="存储路径")
    is_public = Column(Boolean, default=False, comment="是否公开")
    owner_id = Column(String(36), nullable=False, comment="所有者ID")
    status = Column(String(20), default="active", comment="状态")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "模型版本表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    model_id = Column(String(36), ForeignKey("models.id"), nullable=False, comment="模型ID")
    version = Column(String(20), nullable=False, comment="版本号")
    description = Column(String(500), comment="版本描述")
    storage_path = Column(String(500), comment="存储路径")
    framework = Column(String(50), comment="推理框架")     # vLLM, MindIE, custom
    size = Column(BigInteger, default=0, comment="文件总大小(字节)")
    file_count = Column(Integer, default=0, comment="文件数量")
    status = Column(String(20), default="ready", comment="状态")  # uploading, ready, failed
    is_default = Column(Boolean, default=False, comment="是否默认版本")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class ModelFile(Base):
    __tablename__ = "model_files"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "模型文件表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    version_id = Column(String(36), ForeignKey("model_versions.id"), nullable=False, comment="版本ID")
    file_name = Column(String(500), nullable=False, comment="文件名")
    file_path = Column(String(500), comment="存储路径")
    file_size = Column(BigInteger, default=0, comment="文件大小(字节)")
    file_type = Column(String(50), comment="文件类型")     # safetensors, bin, json, txt, other
    status = Column(String(20), default="ready", comment="状态")  # uploading, ready, failed
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
