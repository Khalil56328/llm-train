"""数据集模型"""
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, DateTime, ForeignKey, func
from app.core.database import Base


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "数据集主表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    name = Column(String(200), nullable=False, comment="名称")
    category = Column(String(100), comment="分类")
    type = Column(String(20), default="training", comment="类型: training/evaluation")       # training, evaluation
    data_type = Column(String(20), comment="数据类型")                       # SFT, DPO, KTO, GRPO, GSPO, CPT, general
    eval_dimensions = Column(String(500), comment="评测维度JSON")
    description = Column(String(500), comment="描述")
    source = Column(String(20), default="upload", comment="来源")        # upload, huggingface, oss
    storage_path = Column(String(500), comment="存储路径")
    size = Column(BigInteger, default=0, comment="文件大小(字节)")
    sample_count = Column(Integer, default=0, comment="样本数量")
    is_public = Column(Boolean, default=False, comment="是否公开")
    owner_id = Column(String(36), nullable=False, comment="所有者ID")
    status = Column(String(20), default="ready", comment="状态")         # uploading, processing, ready, failed
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class DatasetFile(Base):
    __tablename__ = "dataset_files"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "数据集文件表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False, comment="数据集ID")
    version_id = Column(String(36), index=True, comment="数据集版本ID(关联dataset_versions.id，为空表示未指定版本)")
    file_name = Column(String(300), nullable=False, comment="文件名称")
    source = Column(String(20), default="local_upload", comment="来源: local_upload, platform")
    status = Column(String(20), default="processing", comment="状态: processing, success, failed")
    size = Column(BigInteger, default=0, comment="文件大小(字节)")
    storage_path = Column(String(500), comment="存储路径")
    batch_id = Column(String(36), index=True, comment="采集批次ID(一次上传的所有文件共享)")
    sample_count = Column(Integer, default=0, comment="样本行数")
    error_message = Column(String(500), comment="失败原因")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "数据集版本表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    dataset_id = Column(String(36), ForeignKey("datasets.id"), nullable=False, comment="数据集ID")
    version = Column(String(20), nullable=False, comment="版本号")
    description = Column(String(500), comment="版本描述")
    storage_path = Column(String(500), comment="存储路径")
    file_count = Column(Integer, default=0, comment="版本文件数")
    size = Column(BigInteger, default=0, comment="版本数据大小(字节)")
    sample_count = Column(Integer, default=0, comment="版本样本数量")
    is_default = Column(Boolean, default=False, comment="是否默认版本")
    created_by = Column(String(50), comment="创建人")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
