"""模型评测模型"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, func, JSON
from app.core.database import Base


class EvaluationTask(Base):
    __tablename__ = "evaluations"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "模型评测表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    name = Column(String(200), nullable=False, comment="评测名称")
    description = Column(String(500), comment="描述")
    eval_type = Column(String(20), default="auto", comment="评测类型: auto/manual")
    is_baseline = Column(Boolean, default=False, comment="是否基线评测")
    dataset_id = Column(String(36), nullable=False, comment="数据集ID")
    dataset_name = Column(String(200), comment="数据集名称")
    deployment_id = Column(String(36), nullable=False, comment="部署ID")
    deployment_name = Column(String(200), comment="部署名称")
    scenes = Column(JSON, default=[], comment="评测场景")          # ["code", "alignment", "agent", "safety", "reasoning"]
    metrics = Column(JSON, default=[], comment="评测指标")          # [{"name":"", "description":""}]
    rating_scale = Column(Integer, default=5, comment="人工评测评分量级(1-10)")
    status = Column(String(20), default="pending", comment="状态: pending/running/completed/failed")
    progress = Column(Integer, default=0, comment="进度百分比 0-100")
    error_message = Column(String(2000), comment="错误信息")
    score = Column(Float, comment="综合评分")
    report_url = Column(String(500), comment="评测报告URL")
    created_by = Column(String(50), comment="创建者")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    finished_at = Column(DateTime, comment="结束时间")


class EvalItem(Base):
    __tablename__ = "eval_items"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "人工评测项表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    eval_id = Column(String(36), nullable=False, index=True, comment="评测任务ID")
    prompt = Column(String(4000), comment="Prompt")
    reference_response = Column(String(4000), comment="参考回答")
    model_response = Column(String(4000), comment="模型回答")
    score = Column(Integer, comment="评分")
    is_evaluated = Column(Boolean, default=False, comment="是否已评估")
    evaluated_by = Column(String(50), comment="评估人")
    evaluated_at = Column(DateTime, comment="评估时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
