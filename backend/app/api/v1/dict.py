"""字典数据接口"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.services.dict_service import DictService

router = APIRouter()


@router.get("/all")
async def get_all_dict(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """获取全部字典数据"""
    svc = DictService(db)
    dict_types = [
        "dataset_category", "dataset_data_type",
        "model_type", "model_spec",
        "train_type", "train_sub_type",
        "eval_scene",
        "operator_category", "operator_type",
        "resource_type", "deploy_framework",
    ]
    data = await svc.get_all_dicts(dict_types)
    # 兼容前端期望的 key 命名
    # 如果没有任何数据（首次启动前），触发 seed
    if not any(v for v in data.values()):
        await svc.seed_default_dicts()
        data = await svc.get_all_dicts(dict_types)

    return {
        "code": 0,
        "message": "success",
        "data": {
            "task_status": _make_dict_items("task_status"),
            "model_type": data.get("model_type", []),
            "model_spec": data.get("model_spec", []),
            "operator_category": data.get("operator_category", []),
            "dataset_data_type": data.get("dataset_data_type", []),
            "dataset_category": data.get("dataset_category", []),
            "deployment_status": _make_dict_items("deployment_status"),
            "resource_type": data.get("resource_type", []),
            "deploy_framework": data.get("deploy_framework", []),
            "train_type": data.get("train_type", []),
            "train_sub_type": data.get("train_sub_type", []),
            "eval_scene": data.get("eval_scene", []),
            "operator_type": data.get("operator_type", []),
        },
    }


def _make_dict_items(category: str) -> list:
    """构建字典条目（兼容旧格式）"""
    items_map = {
        "task_status": [
            ("pending", "待执行", 1), ("running", "执行中", 2),
            ("succeeded", "执行成功", 3), ("failed", "执行失败", 4),
            ("stopped", "已暂停", 5), ("cancelled", "已取消", 6),
        ],
        "deployment_status": [
            ("creating", "创建中", 1), ("running", "运行中", 2),
            ("stopped", "已停止", 3), ("failed", "失败", 4),
            ("deleting", "删除中", 5),
        ],
    }
    items = items_map.get(category, [])
    return [
        {"code": code, "label": label, "value": code, "sortOrder": sort}
        for code, label, sort in items
    ]
