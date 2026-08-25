"""模型部署模型"""
from sqlalchemy import Column, String, Integer, DateTime, Text, func, JSON
from app.core.database import Base


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "模型部署表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    name = Column(String(200), nullable=False, comment="部署名称")
    description = Column(String(500), comment="描述")
    model_id = Column(String(36), nullable=False, comment="模型ID")
    model_name = Column(String(200), comment="模型名称")
    model_version = Column(String(20), comment="模型版本")
    inference_framework = Column(String(20), default="vLLM", comment="推理框架: vLLM/MindIE/custom")
    operator_id = Column(String(36), comment="算子ID")
    operator_version = Column(String(36), comment="算子版本ID（operator_versions.id，32位UUID）")
    params = Column(JSON, default={}, comment="参数JSON")
    env_vars = Column(JSON, default={}, comment="环境变量JSON")
    resource_config = Column(JSON, default={}, comment="资源配置JSON")
    instances = Column(Integer, default=1, comment="实例数")
    container_port = Column(Integer, default=8000, comment="容器端口")
    access_port = Column(Integer, comment="访问端口")
    endpoint = Column(String(500), comment="服务端点")
    engine_command = Column(Text, comment="生成的引擎命令")
    status = Column(String(20), default="creating", comment="状态")              # creating, running, stopped, failed, deleting
    progress = Column(Integer, default=0, comment="进度百分比 0-100")
    error_message = Column(String(2000), comment="错误信息")
    created_by = Column(String(50), comment="创建者")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class DeployInstance(Base):
    __tablename__ = "deploy_instances"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "部署实例表(POD)"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    deploy_id = Column(String(36), nullable=False, index=True, comment="部署ID")
    pod_name = Column(String(200), comment="POD名称")
    status = Column(String(20), default="pending", comment="状态: pending/running/succeeded/failed")
    host_ip = Column(String(50), comment="主机IP")
    pod_ip = Column(String(50), comment="PodIP")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
