"""计算资源池 Pydantic 模型"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ResourcePoolBase(BaseModel):
    """资源池基础字段"""
    name: str = Field(..., min_length=1, max_length=100, description="资源池名称")
    gpu_type: str = Field("A100", max_length=50, description="GPU 类型：A100/V100/H800/A10 等")
    node_count: int = Field(1, ge=1, description="节点数")
    total_gpu: int = Field(0, ge=0, description="GPU 总数")
    available_gpu: int = Field(0, ge=0, description="可用 GPU 数")
    status: str = Field("active", description="状态：active/inactive")
    description: Optional[str] = Field(None, max_length=500, description="资源池描述")


class ResourcePoolCreate(ResourcePoolBase):
    """创建资源池请求体"""
    pass


class ResourcePoolUpdate(BaseModel):
    """更新资源池请求体"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    gpu_type: Optional[str] = Field(None, max_length=50)
    node_count: Optional[int] = Field(None, ge=1)
    total_gpu: Optional[int] = Field(None, ge=0)
    available_gpu: Optional[int] = Field(None, ge=0)
    status: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)


class ResourcePoolOut(ResourcePoolBase):
    """资源池响应体"""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
