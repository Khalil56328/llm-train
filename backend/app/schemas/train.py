"""模型训练 Pydantic 模型"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel


class TrainTaskCreate(BaseModel):
    """创建训练任务请求体（同时接受 camelCase 与 snake_case）"""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=100)
    task_type: str = Field(..., description="sft/rlhf/pt/export")
    task_sub_type: Optional[str] = Field(None, max_length=50, description="任务子类型/模态（入库回显，不参与命令）")
    sub_type: Optional[str] = Field(None, max_length=50)
    base_model_id: Optional[str] = Field(None, max_length=64)
    base_model_name: Optional[str] = Field(None, max_length=200)
    base_model_version: Optional[str] = Field(None, max_length=50)
    operator_id: Optional[str] = Field(None, max_length=64)
    operator_version: Optional[str] = Field(None, max_length=50)
    dataset_id: Optional[str] = Field(None, max_length=64)
    dataset_name: Optional[str] = Field(None, max_length=200, description="数据集名称（入库回显，不参与命令）")
    dataset_version: Optional[str] = Field(None, max_length=50)
    framework: Optional[str] = Field(None, max_length=50, description="训练框架（入库回显，命令生成时定死 swift）")
    val_dataset_id: Optional[str] = Field(None, max_length=64)
    val_dataset_version: Optional[str] = Field(None, max_length=50)
    sft_model_id: Optional[str] = Field(None, max_length=64)
    sft_model_version: Optional[str] = Field(None, max_length=50)
    teacher_model_id: Optional[str] = Field(None, max_length=64)
    teacher_model_version: Optional[str] = Field(None, max_length=50)
    calib_dataset_id: Optional[str] = Field(None, max_length=64)
    calib_dataset_version: Optional[str] = Field(None, max_length=50)
    hyper_params: Dict[str, Any] = Field(default_factory=dict)
    env_vars: Dict[str, Any] = Field(default_factory=dict)
    resource_config: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = Field(None, max_length=1000)


class TrainTaskUpdate(BaseModel):
    """更新训练任务请求体（字段均可选，同时接受 camelCase 与 snake_case）"""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = None
    task_sub_type: Optional[str] = Field(None, max_length=50)
    sub_type: Optional[str] = Field(None, max_length=50)
    base_model_id: Optional[str] = Field(None, max_length=64)
    base_model_name: Optional[str] = Field(None, max_length=200)
    base_model_version: Optional[str] = Field(None, max_length=50)
    operator_id: Optional[str] = Field(None, max_length=64)
    operator_version: Optional[str] = Field(None, max_length=50)
    dataset_id: Optional[str] = Field(None, max_length=64)
    dataset_name: Optional[str] = Field(None, max_length=200)
    dataset_version: Optional[str] = Field(None, max_length=50)
    framework: Optional[str] = Field(None, max_length=50)
    val_dataset_id: Optional[str] = Field(None, max_length=64)
    val_dataset_version: Optional[str] = Field(None, max_length=50)
    sft_model_id: Optional[str] = Field(None, max_length=64)
    sft_model_version: Optional[str] = Field(None, max_length=50)
    teacher_model_id: Optional[str] = Field(None, max_length=64)
    teacher_model_version: Optional[str] = Field(None, max_length=50)
    calib_dataset_id: Optional[str] = Field(None, max_length=64)
    calib_dataset_version: Optional[str] = Field(None, max_length=50)
    hyper_params: Optional[Dict[str, Any]] = None
    env_vars: Optional[Dict[str, Any]] = None
    resource_config: Optional[Dict[str, Any]] = None


class TrainTaskDispatch(BaseModel):
    """提交训练任务执行请求体"""
    id: str = Field(..., max_length=64)
