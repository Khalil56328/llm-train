"""算子中心 Pydantic 模型"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ========== 算子版本（OperatorVersion） ==========
class OperatorVersionBase(BaseModel):
    """算子版本基础字段"""
    name: str = Field(..., min_length=1, max_length=50, description="版本名称")
    description: Optional[str] = Field(None, max_length=500, description="版本描述")
    resource_type: str = Field("CPU", description="资源类型：CPU/GPU")
    base_image: Optional[str] = Field(None, max_length=500, description="基础镜像地址")
    work_dir: Optional[str] = Field(None, max_length=500, description="工作目录")
    start_cmd: Optional[str] = Field(None, max_length=500, description="启动命令")
    mount_dir: Optional[str] = Field(None, max_length=500, description="挂载目录")
    start_params: Optional[Dict[str, Any]] = Field(None, description="启动参数（JSON 对象）")
    is_public: bool = Field(False, description="是否公开")


class OperatorVersionCreate(OperatorVersionBase):
    """创建算子版本请求体"""
    operator_id: Optional[str] = Field(None, description="所属算子 ID（优先使用路径参数）")


class OperatorVersionUpdate(BaseModel):
    """更新算子版本请求体"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    resource_type: Optional[str] = None
    base_image: Optional[str] = None
    work_dir: Optional[str] = None
    start_cmd: Optional[str] = None
    mount_dir: Optional[str] = None
    start_params: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None


class OperatorVersionOut(OperatorVersionBase):
    """算子版本响应体"""
    id: str
    operator_id: str
    image_address: Optional[str] = None
    image_name: Optional[str] = None
    creator: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ========== 算子（Operator） ==========
class OperatorBase(BaseModel):
    """算子基础字段"""
    name: str = Field(..., min_length=1, max_length=50, description="算子名称")
    category: str = Field(..., description="算子类型（细分类目，如 预训练 / 微调）")
    type: str = Field("training", description="算子大类：training/inference/data/other")
    training_framework: Optional[str] = Field(None, max_length=50, description="训练框架：PyTorch/TensorFlow/JAX/PaddlePaddle等")
    training_method: Optional[str] = Field(None, max_length=50, description="训练方法：SFT/LoRA/DPO/RLHF/Pretrain等")
    description: Optional[str] = Field(None, max_length=500, description="算子描述")


class OperatorCreate(OperatorBase):
    """创建算子请求体"""
    is_public: bool = False


class OperatorUpdate(BaseModel):
    """更新算子请求体"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    category: Optional[str] = None
    type: Optional[str] = None
    training_framework: Optional[str] = Field(None, max_length=50)
    training_method: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None


class OperatorOut(OperatorBase):
    """算子响应体"""
    id: str
    version_count: int = 0
    owner: Optional[str] = None
    owner_name: Optional[str] = None
    is_public: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OperatorWithVersionsOut(OperatorOut):
    """算子详情（含版本列表）"""
    versions: List[OperatorVersionOut] = Field(default_factory=list)


# ========== 镜像（Image） ==========
class ImageOut(BaseModel):
    """镜像响应体（用于镜像选择弹框）"""
    id: str
    name: str
    address: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
