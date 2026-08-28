"""应用配置"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "大模型训推平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 服务器对外 IP（模型部署模块生成 endpoint / 实例 host_ip 用，需可被外部真实调用）
    # 留空则部署时自动探测本机对外网卡 IP；多网卡或探测不准时请显式填写
    SERVER_IP: str = ""

    # 数据库（MySQL 8.0，asyncmy 驱动；默认本机 127.0.0.1，
    # 前后端一体部署，MySQL/Redis/MinIO 均为本机服务，无需跨主机连接串）
    DATABASE_URL: str = "mysql+asyncmy://llm_train:llm_train_2026@localhost:3306/llm_train?charset=utf8mb4"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # 存储：minio / local（Notebook 单机默认 local，MinIO 不可用时 storage.py 自动降级本地磁盘）
    STORAGE_TYPE: str = "local"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "models"
    MINIO_SECURE: bool = False

    # 上传限制（数据集文件）
    UPLOAD_MAX_SIZE_MB: int = 1024        # 单文件最大 1GB
    UPLOAD_MAX_FILES_PER_BATCH: int = 50  # 单批次最大文件数
    UPLOAD_ALLOWED_EXTS: str = ".json,.jsonl,.csv,.txt,.parquet,.gz,.zip,.tar"

    # 模型文件上传限制
    MODEL_UPLOAD_MAX_SIZE_MB: int = 10240        # 单文件最大 10GB
    MODEL_UPLOAD_MAX_FILES_PER_BATCH: int = 50   # 单批次最大文件数

    # 训练
    # 运行载体: local(本机直接执行 swift/vllm 命令，Notebook 单机默认) / nvidia-docker(容器运行时)
    TRAIN_CONTAINER_RUNTIME: str = "local"
    TRAIN_WORKSPACE: str = "workspace"
    # 任务执行模式: auto(检测 swift 命令) / mock(本地模拟) / real(真实执行)
    TRAIN_EXECUTION_MODE: str = "auto"
    # 本地存储根目录（模型产物 / 评测报告 / 上传文件）
    LOCAL_STORAGE_DIR: str = "storage"
    # 前端 dist 目录（非空时由 FastAPI 托管 SPA，适用于无 Nginx 场景，如 ModelScope Notebook）
    FRONTEND_DIST_DIR: str = ""

    # 部署时自动录入的默认模型（ModelScope 模型 ID，如 Qwen/Qwen2.5-0.5B-Instruct）
    # 由部署脚本（deploy/common/download_models.sh）下载到 backend/workspace/models/<模型名小写>/，
    # 下载完成后立即模拟页面「创建模型 + 上传模型文件」逻辑录入模型库
    # （deploy/common/seed_model_record.py：写 models / model_versions / model_files，
    #  storage_path 与文件指向真实下载路径，广场/我的模型库可见）；后端启动时的
    # ModelSeedService 作为幂等兜底。留空则不自动录入
    SEED_MODEL_ID: str = ""
    SEED_MODEL_VENDOR: str = "ModelScope"
    SEED_MODEL_TYPE: str = "dialogue"      # dialogue / vision / embedding / ...
    SEED_MODEL_SPEC: str = "below-10b"     # below-10b / 10b-50b / 50b-100b / above-100b

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
