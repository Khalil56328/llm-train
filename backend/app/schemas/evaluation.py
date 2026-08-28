"""模型评测 Pydantic 模型

注意：字段使用驼峰命名，与 EvalService 读取键、前端提交字段、_eval_to_dict 输出保持一致。
（不要改成 snake_case，否则 service 层 data.get("datasetId") 等会取不到值）
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class EvaluationCreate(BaseModel):
    """创建评测任务请求体"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    evalType: str = Field("auto", description="auto/manual")
    isBaseline: bool = False
    datasetId: str = Field(..., min_length=1, max_length=64)
    datasetName: Optional[str] = Field(None, max_length=200)
    datasetVersion: Optional[str] = Field(None, max_length=50, description="数据集版本号")
    deploymentId: str = Field(..., min_length=1, max_length=64)
    deploymentName: Optional[str] = Field(None, max_length=200)
    scenes: List[str] = Field(default_factory=list)
    # 评估指标为对象数组：[{"name": "...", "description": "..."}]，与 ORM 注释及前端提交格式一致
    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    ratingScale: int = Field(5, ge=2, le=10)


class EvalItemScore(BaseModel):
    """人工评测项评分请求体"""
    score: int = Field(..., ge=0, le=10)


class EvaluationUpdate(BaseModel):
    """更新评测任务请求体（字段均可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    reportUrl: Optional[str] = Field(None, max_length=1000)
