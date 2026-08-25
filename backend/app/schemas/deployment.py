"""模型部署 Pydantic 模型

注意：字段使用驼峰命名，与 DeployService 读取键、前端提交字段、_deploy_to_dict 输出保持一致。
（不要改成 snake_case，否则 service 层 data.get("modelId") 等会取不到值）
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DeploymentCreate(BaseModel):
    """创建部署请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    modelId: str = Field(..., min_length=1, max_length=64)
    modelName: Optional[str] = Field(None, max_length=200)
    modelVersion: Optional[str] = Field(None, max_length=50)
    inferenceFramework: str = Field("vLLM", max_length=50)
    operatorId: Optional[str] = Field(None, max_length=64)
    operatorVersion: Optional[str] = Field(None, max_length=50)
    params: Dict[str, Any] = Field(default_factory=dict)
    envVars: Dict[str, Any] = Field(default_factory=dict)
    resourceConfig: Dict[str, Any] = Field(default_factory=dict)
    instances: int = Field(1, ge=1, le=32)
    containerPort: int = Field(8000, ge=1, le=65535)
    accessPort: Optional[int] = Field(None, ge=1, le=65535)
    endpoint: Optional[str] = Field(None, max_length=500)


class DeploymentTest(BaseModel):
    """部署推理测试请求体"""
    prompt: str = Field(..., min_length=1, max_length=8000)


class DeploymentUpdate(BaseModel):
    """更新部署请求体（字段均可选，驼峰命名）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    modelId: Optional[str] = Field(None, max_length=64)
    modelName: Optional[str] = Field(None, max_length=200)
    modelVersion: Optional[str] = Field(None, max_length=50)
    inferenceFramework: Optional[str] = Field(None, max_length=50)
    operatorId: Optional[str] = Field(None, max_length=64)
    operatorVersion: Optional[str] = Field(None, max_length=50)
    instances: Optional[int] = Field(None, ge=1, le=32)
    containerPort: Optional[int] = Field(None, ge=1, le=65535)
    accessPort: Optional[int] = Field(None, ge=1, le=65535)
    params: Optional[Dict[str, Any]] = None
    envVars: Optional[Dict[str, Any]] = None
    resourceConfig: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
