"""API v1 路由汇总"""
from fastapi import APIRouter
from app.api.v1 import auth, operators, datasets, models, training, deployments, evaluations, dict, notifications, images, resources, inference

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(operators.router, prefix="/operators", tags=["算子中心"])
api_router.include_router(images.router, prefix="/images", tags=["镜像资源"])
api_router.include_router(resources.router, prefix="/resource-pools", tags=["资源管理"])
api_router.include_router(datasets.router, prefix="/datasets", tags=["数据中心"])
api_router.include_router(models.router, prefix="/models", tags=["模型中心"])
api_router.include_router(training.router, prefix="/train-tasks", tags=["模型训练"])
api_router.include_router(deployments.router, prefix="/deployments", tags=["模型部署"])
api_router.include_router(inference.router, prefix="", tags=["在线推理"])
api_router.include_router(evaluations.router, prefix="/evaluations", tags=["模型评测"])
api_router.include_router(dict.router, prefix="/dict", tags=["字典数据"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知消息"])
