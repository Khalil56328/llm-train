"""认证 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user, require_roles
from app.core.response import success_response, error_response
from app.services.auth_service import AuthService
from app.schemas.user import LoginRequest, UserCreate, UserUpdate

router = APIRouter()


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    svc = AuthService(db)
    result = await svc.login(req.username, req.password)
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return success_response(result)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return success_response(user)


# 平台侧边栏菜单（与前端 src/router/index.ts 路由对应）
_PLATFORM_MENU = [
    {"id": "home", "name": "首页", "path": "/home", "icon": "HomeFilled", "order": 0},
    {
        "id": "operator",
        "name": "算子中心",
        "path": "/operator/management",
        "icon": "Monitor",
        "order": 1,
        "children": [
            {"id": "operator-management", "name": "算子管理", "path": "/operator/management", "icon": "Menu", "order": 1},
            {"id": "operator-plaza", "name": "算子广场", "path": "/operator/plaza", "icon": "Shop", "order": 2},
        ],
    },
    {
        "id": "data",
        "name": "数据中心",
        "path": "/data/training",
        "icon": "Folder",
        "order": 2,
        "children": [
            {"id": "data-training", "name": "训练数据集", "path": "/data/training", "icon": "Folder", "order": 1},
            {"id": "data-evaluation", "name": "评测数据集", "path": "/data/evaluation", "icon": "FolderChecked", "order": 2},
            {"id": "data-plaza", "name": "数据集广场", "path": "/data/plaza", "icon": "Shop", "order": 3},
        ],
    },
    {
        "id": "train",
        "name": "模型训练",
        "path": "/train/fine-tune",
        "icon": "Cpu",
        "order": 3,
        "children": [
            {"id": "train-fine-tune", "name": "模型微调", "path": "/train/fine-tune", "icon": "Cpu", "order": 1},
            {"id": "train-alignment", "name": "偏好对齐", "path": "/train/alignment", "icon": "Connection", "order": 2},
            {"id": "train-compression", "name": "模型压缩", "path": "/train/compression", "icon": "Sort", "order": 3},
            {"id": "train-pretrain", "name": "预训练", "path": "/train/pretrain", "icon": "DataBoard", "order": 4},
            {"id": "train-scene", "name": "场景训练", "path": "/train/scene", "icon": "TrendCharts", "order": 5},
        ],
    },
    {
        "id": "model",
        "name": "模型中心",
        "path": "/model/my-library",
        "icon": "Files",
        "order": 4,
        "children": [
            {"id": "model-library", "name": "我的模型库", "path": "/model/my-library", "icon": "Files", "order": 1},
            {"id": "model-plaza", "name": "模型库广场", "path": "/model/plaza", "icon": "Shop", "order": 2},
        ],
    },
    {
        "id": "service",
        "name": "模型服务",
        "path": "/service/deployment",
        "icon": "Platform",
        "order": 5,
        "children": [
            {"id": "service-deployment", "name": "模型部署", "path": "/service/deployment", "icon": "Platform", "order": 1},
            {"id": "service-evaluation", "name": "模型评测", "path": "/service/evaluation", "icon": "Histogram", "order": 2},
        ],
    },
    {
        "id": "ops",
        "name": "运维中心",
        "path": "/ops/resource",
        "icon": "Setting",
        "order": 6,
        "children": [
            {"id": "ops-resource", "name": "资源管理", "path": "/ops/resource", "icon": "Setting", "order": 1},
            {"id": "ops-images", "name": "镜像管理", "path": "/ops/images", "icon": "Box", "order": 2},
        ],
    },
]


@router.get("/menu")
async def menu(_user: dict = Depends(get_current_user)):
    return success_response(_PLATFORM_MENU)


# ========== 用户管理（仅管理员） ==========
@router.get("/users")
async def list_users(
    page_index: int = 1,
    page_size: int = 20,
    keyword: str = None,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(require_roles("super_admin", "admin")),
):
    svc = AuthService(db)
    result = await svc.list_users(page_index=page_index, page_size=page_size, keyword=keyword)
    return success_response(result)


@router.post("/users")
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_roles("super_admin", "admin"))):
    svc = AuthService(db)
    result = await svc.create_user(data.model_dump())
    return success_response(result)


@router.put("/users/{user_id}")
async def update_user(user_id: str, data: UserUpdate, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_roles("super_admin", "admin"))):
    # 不允许普通管理员把用户提升为超管/删除超管
    if _user["role"] != "super_admin" and data.role == "super_admin":
        raise HTTPException(status_code=403, detail="仅超级管理员可授予 super_admin 角色")
    svc = AuthService(db)
    result = await svc.update_user(user_id, data.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="用户不存在")
    return success_response(result)


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db), _user: dict = Depends(require_roles("super_admin", "admin"))):
    if user_id == _user["id"]:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    svc = AuthService(db)
    target = await svc.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target["role"] == "super_admin" and _user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="仅超级管理员可删除超管账号")
    ok = await svc.delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return success_response({"message": "删除成功"})
