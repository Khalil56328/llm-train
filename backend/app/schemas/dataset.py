"""数据中心 Pydantic 模型"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    """创建数据集请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    type: str = Field("training", description="training/evaluation")
    data_type: Optional[str] = Field(None, max_length=50, description="文本/对话/图像等")
    eval_dimensions: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    source: str = Field("upload", description="upload/custom")
    storage_path: Optional[str] = Field(None, max_length=1000)
    size: int = Field(0, ge=0)
    sample_count: int = Field(0, ge=0)
    is_public: bool = False
    status: str = Field("ready")


class DatasetUpdate(BaseModel):
    """更新数据集请求体（字段均可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    data_type: Optional[str] = Field(None, max_length=50)
    eval_dimensions: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    storage_path: Optional[str] = Field(None, max_length=1000)
    is_public: Optional[bool] = None
    status: Optional[str] = None


class DatasetVersionCreate(BaseModel):
    """创建数据集版本请求体"""
    version: str = Field("v1", max_length=50)
    storage_path: Optional[str] = Field(None, max_length=1000)
    is_default: bool = False


class DatasetVersionUpdate(BaseModel):
    """更新数据集版本请求体"""
    version: Optional[str] = Field(None, max_length=50)
    storage_path: Optional[str] = Field(None, max_length=1000)
    is_default: Optional[bool] = None
    status: Optional[str] = None


class DatasetFileCreate(BaseModel):
    """数据集文件登记请求体"""
    file_name: str = Field(..., min_length=1, max_length=255)
    source: str = Field("local_upload", description="采集方式(数据来源): local_upload/platform")
    status: str = Field("processing", description="processing/success/failed")
    size: int = Field(0, ge=0)
    storage_path: Optional[str] = Field(None, max_length=1000)
    batch_id: Optional[str] = Field(None, max_length=36, description="采集批次ID")
    sample_count: int = Field(0, ge=0, description="样本行数")
    error_message: Optional[str] = Field(None, max_length=500, description="失败原因")


class DatasetCompareReq(BaseModel):
    """数据集对比请求体"""
    datasetIds: list = Field(..., min_length=2, max_length=4)
