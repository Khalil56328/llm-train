"""算子模型（不含 status 字段）"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func, JSON, Integer
from app.core.database import Base


class Operator(Base):
    __tablename__ = "operators"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "算子主表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    name = Column(String(100), nullable=False, comment="算子名称")
    category = Column(String(50), nullable=False, comment="分类")     # 预训练 / 大模型微调 / 模型蒸馏 / 模型推理 ...
    type = Column(String(20), default="training", comment="类型")      # training, inference, data, other
    training_framework = Column(String(50), comment="训练框架")         # PyTorch / TensorFlow / JAX / PaddlePaddle 等
    training_method = Column(String(50), comment="训练方法")            # SFT / LoRA / DPO / RLHF / Pretrain 等
    description = Column(String(500), comment="描述")
    is_public = Column(Boolean, default=False, comment="是否公开")
    owner_id = Column(String(36), nullable=False, comment="所有者ID")
    version_count = Column(Integer, default=0, comment="版本数量")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class OperatorVersion(Base):
    __tablename__ = "operator_versions"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "算子版本表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    operator_id = Column(String(36), ForeignKey("operators.id"), nullable=False, comment="算子ID")
    name = Column(String(50), nullable=False, comment="版本名称")
    description = Column(String(500), comment="版本描述")
    resource_type = Column(String(20), default="CPU", comment="资源类型")
    base_image = Column(String(500), comment="基础镜像")
    work_dir = Column(String(500), comment="工作目录")
    start_cmd = Column(String(500), comment="启动命令")
    mount_dir = Column(String(500), comment="挂载目录")
    start_params = Column(JSON, comment="启动参数JSON")
    is_public = Column(Boolean, default=False, comment="是否公开")
    creator = Column(String(50), comment="创建者")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
