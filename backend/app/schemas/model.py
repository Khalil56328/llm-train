"""模型中心 Pydantic 模型"""
from typing import Optional, List
from pydantic import BaseModel, Field


class ModelCreate(BaseModel):
    """创建模型请求体"""
    name: str = Field(..., min_length=1, max_length=200)
    type: Optional[str] = Field(None, max_length=50)
    spec: Optional[str] = Field(None, max_length=100)
    vendor: Optional[str] = Field(None, max_length=100)
    version: str = Field("v1", max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[str] = Field(None, max_length=500)
    iconUrl: Optional[str] = Field(None, max_length=1000)
    storagePath: Optional[str] = Field(None, max_length=1000)
    isPublic: bool = False
    status: str = Field("active", max_length=20)


class ModelUpdate(BaseModel):
    """更新模型请求体（字段均可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[str] = Field(None, max_length=50)
    spec: Optional[str] = Field(None, max_length=100)
    vendor: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[str] = Field(None, max_length=500)
    iconUrl: Optional[str] = Field(None, max_length=1000)
    storagePath: Optional[str] = Field(None, max_length=1000)
    isPublic: Optional[bool] = None
    status: Optional[str] = Field(None, max_length=20)


class ModelCompareReq(BaseModel):
    """模型对比请求体"""
    modelIds: List[str] = Field(..., min_length=2, max_length=4)


class ModelVersionCreate(BaseModel):
    """创建模型版本请求体"""
    version: str = Field("v1", max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    storagePath: Optional[str] = Field(None, max_length=1000)
    framework: Optional[str] = Field(None, max_length=50)
    size: int = Field(0, ge=0)
    fileCount: int = Field(0, ge=0)
    status: str = Field("ready", max_length=20)
    isDefault: bool = False


class ModelVersionUpdate(BaseModel):
    """更新模型版本请求体（字段均可选）"""
    version: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    storagePath: Optional[str] = Field(None, max_length=1000)
    framework: Optional[str] = Field(None, max_length=50)
    size: Optional[int] = Field(None, ge=0)
    fileCount: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, max_length=20)
    isDefault: Optional[bool] = None


class ModelFileCreate(BaseModel):
    """模型文件登记请求体"""
    fileName: str = Field(..., min_length=1, max_length=255)
    filePath: Optional[str] = Field(None, max_length=1000)
    fileSize: int = Field(0, ge=0)
    fileType: str = Field("other", max_length=50)
    status: str = Field("ready", max_length=20)
