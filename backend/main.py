"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal
import app.models  # noqa: F401  # 导入模型确保表注册到 metadata
from app.api.v1 import api_router
from app.tasks.executor import storage_dir
from app.ws.train import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：创建数据库表（生产环境应使用 Alembic）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 同步已存在表的缺失列（create_all 不会修改已有表）
    try:
        from app.core.schema_sync import sync_schema
        await sync_schema()
    except Exception as e:
        print(f"[WARN] Schema sync failed: {e}")

    # 初始化基础数据（管理员用户 + 字典数据 + 默认模型 + 镜像 + 资源池）
    # 默认模型由部署脚本下载到 workspace/models/ 后在此自动录入（SEED_MODEL_ID 配置）
    async with AsyncSessionLocal() as seed_db:
        try:
            from app.services.auth_service import AuthService
            from app.services.dict_service import DictService
            from app.services.model_seed_service import ModelSeedService
            from app.services.image_service import ImageService
            from app.services.resource_service import ResourcePoolService

            auth_svc = AuthService(seed_db)
            await auth_svc.seed_admin_user()

            dict_svc = DictService(seed_db)
            await dict_svc.seed_default_dicts()

            model_seed = ModelSeedService(seed_db)
            inserted = await model_seed.seed()

            image_svc = ImageService(seed_db)
            inserted_images = await image_svc.seed_defaults()

            pool_svc = ResourcePoolService(seed_db)
            inserted_pools = await pool_svc.seed_defaults()

            await seed_db.commit()
            if inserted:
                print(f"[INFO] Model seed: inserted {inserted} models")
            if inserted_images:
                print(f"[INFO] Image seed: inserted {inserted_images} images")
            if inserted_pools:
                print(f"[INFO] ResourcePool seed: inserted {inserted_pools} resource pools")
        except Exception as e:
            await seed_db.rollback()
            # 种子数据初始化失败不影响启动
            print(f"[WARN] Seed data init failed: {e}")

    yield
    # 关闭时
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # 通配来源 + 凭据是浏览器禁止的非法组合；前端使用 Bearer 头（Authorization），
    # 无 cookie 凭据，故关闭 allow_credentials（测试环境同域部署下 CORS 不生效）
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(api_router, prefix="/api")
# WebSocket 实时日志
app.include_router(ws_router, prefix="/api")

# 静态文件（评测报告 / 上传文件等）
_static_dir = storage_dir()
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# 健康检查
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


# 前端 SPA 静态托管（无 Nginx 场景：ModelScope Notebook / 单机直跑）
# 设置 FRONTEND_DIST_DIR 指向 web-ui/dist 后启用，一个端口同时提供前端 + /api + /static
if settings.FRONTEND_DIST_DIR:
    _dist_dir = Path(settings.FRONTEND_DIST_DIR).expanduser().resolve()
    _index_html = _dist_dir / "index.html"
    if _index_html.is_file():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_dist_dir / "assets")),
            name="frontend-assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            # 已注册的 /api、/static、/assets 路由优先匹配，不会进入此回退
            if full_path.startswith(("api/", "static/", "assets/", "docs", "openapi.json")):
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = (_dist_dir / full_path).resolve()
            try:
                candidate.relative_to(_dist_dir)
            except ValueError:
                candidate = _dist_dir
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(_index_html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
