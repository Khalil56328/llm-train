"""镜像资源 Pydantic 模型"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ImageBase(BaseModel):
    """镜像基础字段"""
    name: str = Field(..., min_length=1, max_length=100, description="镜像名称")
    address: str = Field(..., min_length=1, max_length=500, description="镜像完整地址")
    resource_type: str = Field("CPU", description="资源类型：CPU/GPU")
    description: Optional[str] = Field(None, max_length=500, description="镜像描述")


class ImageCreate(ImageBase):
    """创建镜像请求体"""
    pass


class ImageUpdate(BaseModel):
    """更新镜像请求体"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    resource_type: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)


class ImageOut(ImageBase):
    """镜像响应体"""
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
