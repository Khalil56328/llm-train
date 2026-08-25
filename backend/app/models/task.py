"""训练任务模型"""
from sqlalchemy import Column, String, Integer, DateTime, Float, Text, func, JSON
from app.core.database import Base


class TrainTask(Base):
    __tablename__ = "train_tasks"
    __table_args__ = {
        "mysql_engine": "InnoDB",
        "mysql_charset": "utf8mb4",
        "comment": "训练任务表"
    }

    id = Column(String(36), primary_key=True, comment="主键")
    name = Column(String(200), nullable=False, comment="任务名称")
    task_type = Column(String(20), nullable=False, comment="任务类型: fine-tune/alignment/compression/pretrain/scene")
    task_sub_type = Column(String(50), comment="任务子类型/模态: text-generation/image-generation/image-understanding等")
    sub_type = Column(String(50), comment="子类型: LoRA微调/DPO/KTO/GRPO等")
    status = Column(String(20), default="pending", comment="状态: pending/running/succeeded/failed/stopped")
    progress = Column(Integer, default=0, comment="进度百分比 0-100")
    error_message = Column(String(2000), comment="错误信息")
    base_model_id = Column(String(36), comment="基座模型ID")
    base_model_name = Column(String(200), comment="基座模型名称")
    base_model_version = Column(String(20), comment="基座模型版本")
    operator_id = Column(String(36), comment="算子ID")
    operator_version = Column(String(36), comment="算子版本ID（operator_versions.id，32位UUID）")
    dataset_id = Column(String(36), comment="数据集ID")
    dataset_name = Column(String(200), comment="数据集名称（页面展示用，不参与训练命令）")
    dataset_version = Column(String(20), comment="数据集版本")
    framework = Column(String(50), comment="训练框架（页面选择，入库回显；命令生成时定死 swift）")
    val_dataset_id = Column(String(36), comment="验证数据集ID（页面选择，入库回显）")
    val_dataset_version = Column(String(20), comment="验证数据集版本")
    sft_model_id = Column(String(36), comment="SFT模型ID（对齐任务，页面选择，入库回显）")
    sft_model_version = Column(String(20), comment="SFT模型版本")
    teacher_model_id = Column(String(36), comment="教师模型ID（压缩任务，页面选择，入库回显）")
    teacher_model_version = Column(String(20), comment="教师模型版本")
    calib_dataset_id = Column(String(36), comment="校准数据集ID（压缩任务，页面选择，入库回显）")
    calib_dataset_version = Column(String(20), comment="校准数据集版本")
    hyper_params = Column(JSON, default={}, comment="超参JSON")
    env_vars = Column(JSON, default={}, comment="环境变量JSON")
    resource_config = Column(JSON, default={}, comment="资源配置JSON")
    output_model_id = Column(String(36), comment="产出模型ID")
    output_model_name = Column(String(200), comment="产出模型名称")
    engine_command = Column(Text, comment="生成的引擎命令")
    description = Column(String(500), comment="描述")
    created_by = Column(String(50), comment="创建者")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    started_at = Column(DateTime, comment="开始时间")
    finished_at = Column(DateTime, comment="结束时间")
