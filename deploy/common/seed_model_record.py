#!/usr/bin/env python3
"""把「已下载到工作目录的模型文件」录入模型库，模拟「我的模型库 → 创建模型 → 上传模型文件」页面逻辑。

背景
----
部署流程（deploy/common/download_models.sh，被 deploy/ubuntu/init_env.sh 与
deploy/notebook/init_env.sh 调用）会把默认模型（backend/.env 的 SEED_MODEL_ID）真实下载到
backend/workspace/models/<模型名小写>/。本脚本在初始化阶段（后端首次启动前）就把该目录
录入数据库（models / model_versions / model_files 三张表），使「我的模型库 / 模型库广场」
立即可见该模型，且文件指向真实下载的模型文件（storage_path / file_path 均为真实绝对路径）。

与页面新增逻辑完全一致（复用 ModelService，即页面「创建模型」POST /api/models、
「新建版本」POST /api/models/{id}/versions、「上传文件」POST .../files 的等价实现）：
  1) create_model   —— 创建模型记录（默认公开，模型库广场可见）
  2) create_version —— 创建默认版本（v1.0 / vLLM）
  3) create_file    —— 对目录下每个文件逐条登记 model_files（file_path 指向真实文件）

幂等：已按 storage_path 录入过的模型自动跳过，可安全重复执行（重启、补录均无副作用）。

用法（任意目录执行；需已安装后端依赖，Ubuntu 用 backend/.venv/bin/python）：
  backend/.venv/bin/python deploy/common/seed_model_record.py --model Qwen/Qwen2.5-0.5B-Instruct
  python3 deploy/common/seed_model_record.py --model X --root /data/workspace --dir models/my-model
  python3 deploy/common/seed_model_record.py --no-public --model X   # 不公开（仅我的模型库可见）

参数：
  --model <hub_id>  ModelScope 模型 ID（默认读取 backend/.env 的 SEED_MODEL_ID）
  --root <path>     工作目录根（默认 backend/workspace，支持绝对/相对路径）
  --dir <rel>       模型相对目录（默认 models/<模型名小写>）
  --no-public       不公开（默认公开，模型库广场可见）

退出码：0 = 已录入 / 已存在跳过 / 目录不存在跳过；1 = 数据库或录入失败。
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 定位项目根与 backend 目录，并切换到 backend（使 app.core.config 读取 backend/.env）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import engine, Base, AsyncSessionLocal  # noqa: E402
import app.models  # noqa: E402, F401  # 注册所有表到 metadata
from app.models.model import Model  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services.model_service import ModelService  # noqa: E402


def log(msg: str) -> None:
    print(f"[seed-model] {msg}", flush=True)


def _file_type(name: str) -> str:
    """扩展名 → 文件类型（与模型文件上传的 file_type 取值保持一致）"""
    ext = Path(name).suffix.lower().lstrip(".")
    known = {
        "safetensors": "safetensors", "bin": "bin", "json": "json", "txt": "txt",
        "gguf": "gguf", "onnx": "onnx", "model": "model", "pt": "pt",
        "pth": "pth", "ckpt": "ckpt", "md": "md",
    }
    return known.get(ext, "other")


def _scan_files(abs_dir: Path) -> List[Dict]:
    """递归扫描目录下所有文件（跳过隐藏文件），返回 name/path/size/type"""
    files: List[Dict] = []
    for root, _dirs, names in os.walk(abs_dir):
        for n in sorted(names):
            if n.startswith("."):
                continue
            p = Path(root) / n
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            files.append({
                "name": str(p.relative_to(abs_dir)).replace("\\", "/"),
                "path": str(p),
                "size": size,
                "type": _file_type(n),
            })
    return files


def _resolve_workspace_root() -> Path:
    """解析工作目录根（兼容绝对路径形式的 TRAIN_WORKSPACE）"""
    ws = (settings.TRAIN_WORKSPACE or "workspace").strip()
    if os.path.isabs(ws):
        return Path(ws)
    return BACKEND_DIR / ws


async def _ensure_schema() -> None:
    """建表 + 补齐缺失列（与 main.py 启动逻辑一致，供后端首次启动前使用）"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        from app.core.schema_sync import sync_schema
        await sync_schema()
    except Exception as exc:  # noqa: BLE001
        log(f"[WARN] Schema sync failed: {exc}")


async def _seed_one(hub_id: str, abs_dir: Path, is_public: bool) -> bool:
    """录入单个模型（模拟页面新增逻辑），返回是否本次新录入（幂等）"""
    async with AsyncSessionLocal() as db:
        # 幂等：已按 storage_path 录入过的模型跳过
        existing = await db.execute(
            select(Model.id).where(Model.storage_path == str(abs_dir)).limit(1)
        )
        if existing.scalar_one_or_none():
            log(f"模型已录入过（{abs_dir}），跳过")
            return False

        # 所有者：优先 admin（与种子逻辑一致）；不存在则先创建
        await AuthService(db).seed_admin_user()
        result = await db.execute(select(User).where(User.username == "admin").limit(1))
        admin = result.scalar_one_or_none()
        owner_id = admin.id if admin else "system"

        files = _scan_files(abs_dir)
        if not files:
            log(f"模型目录为空（{abs_dir}），跳过")
            return False
        total_size = sum(f["size"] for f in files)
        name = hub_id.rsplit("/", 1)[-1]

        svc = ModelService(db)
        # 1) 创建模型（等价页面「创建模型」）
        model = await svc.create_model({
            "name": name,
            "type": settings.SEED_MODEL_TYPE,
            "spec": settings.SEED_MODEL_SPEC,
            "vendor": settings.SEED_MODEL_VENDOR,
            "version": "v1.0",
            "description": f"部署时自动录入的默认模型（{hub_id}），由 ModelScope 下载",
            "tags": '["默认模型"]',
            "iconUrl": "",
            "storagePath": str(abs_dir),
            "isPublic": is_public,
            "status": "active",
        }, owner_id=owner_id)
        # 2) 创建默认版本（等价页面「新建版本」）
        version = await svc.create_version(model["id"], {
            "version": "v1.0",
            "description": "部署时自动录入的默认版本",
            "storagePath": str(abs_dir),
            "framework": "vLLM",
            "size": total_size,
            "fileCount": len(files),
            "status": "ready",
            "isDefault": True,
        })
        # 3) 逐条登记真实文件（等价页面「上传模型文件」：file_path 指向真实下载文件）
        for f in files:
            await svc.create_file(version["id"], {
                "fileName": f["name"],
                "filePath": f["path"],
                "fileSize": f["size"],
                "fileType": f["type"],
                "status": "ready",
            })
        await db.commit()
        log(f"已录入模型 {name}（{len(files)} 个文件，共 {total_size / 1024 / 1024:.1f} MB）"
            f" -> {abs_dir}")
        return True


async def main() -> int:
    parser = argparse.ArgumentParser(description="录入已下载模型到模型库（模拟页面新增逻辑）")
    parser.add_argument("--model", default="", help="ModelScope 模型 ID（默认取 SEED_MODEL_ID）")
    parser.add_argument("--root", default="", help="工作目录根（默认 backend/workspace）")
    parser.add_argument("--dir", default="", help="模型相对目录（默认 models/<模型名小写>）")
    parser.add_argument("--no-public", action="store_true", help="不公开（默认公开）")
    args = parser.parse_args()

    hub_id = (args.model or settings.SEED_MODEL_ID or "").strip().strip('"')
    if not hub_id:
        log("未指定 --model 且 SEED_MODEL_ID 未配置，跳过（如需录入请传 --model）")
        return 0

    name = hub_id.rsplit("/", 1)[-1]
    root = Path(args.root) if args.root else _resolve_workspace_root()
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    rel_dir = args.dir or f"models/{name.lower()}"
    abs_dir = root / rel_dir

    if not abs_dir.is_dir():
        log(f"模型目录不存在（{abs_dir}），跳过（请先下载：bash deploy/common/download_models.sh --model {hub_id}）")
        return 0

    try:
        await _ensure_schema()
        inserted = await _seed_one(hub_id, abs_dir, is_public=not args.no_public)
    except Exception as exc:  # noqa: BLE001
        log(f"[ERROR] 录入失败（MySQL 未就绪或依赖缺失？）: {exc}")
        return 1
    if inserted:
        log("完成（我的模型库 / 模型库广场 可见；storage_path 与文件均指向真实路径）")
    else:
        log("跳过（已存在或目录为空）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
