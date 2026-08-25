"""训练任务日志与指标模型

seq 为任务内单调递增序号（由执行器在应用侧生成），
用于日志/指标的稳定排序与 WebSocket 增量推送游标。
"""
from sqlalchemy import Column, String, BigInteger, Integer, Float, DateTime, Text, func
from app.core.database import Base


class TrainTaskLog(Base):
    __tablename__ = "train_task_logs"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "训练任务日志表",
    }

    id = Column(String(36), primary_key=True, comment="主键")
    seq = Column(BigInteger, index=True, comment="任务内序号")
    task_id = Column(String(36), nullable=False, index=True, comment="训练任务ID")
    time = Column(DateTime, comment="日志时间")
    level = Column(String(10), default="INFO", comment="日志级别")
    message = Column(Text, comment="日志内容")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class TrainTaskMetric(Base):
    __tablename__ = "train_task_metrics"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "训练任务指标表",
    }

    id = Column(String(36), primary_key=True, comment="主键")
    seq = Column(BigInteger, index=True, comment="任务内序号")
    task_id = Column(String(36), nullable=False, index=True, comment="训练任务ID")
    step = Column(Integer, default=0, comment="步数")
    loss = Column(Float, comment="Loss")
    lr = Column(Float, comment="学习率")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
