"""模型初始化服务

在系统启动时，把「部署脚本已下载到工作目录的默认模型」录入模型库
（models / model_versions / model_files 三张表），使「模型库广场」和
「我的模型库」有真实可用的内容。

不再内置演示占位模型：旧版种子模型的 storage_path 是磁盘上不存在的
占位路径（如 models/qwen/qwen2.5-7b-instruct），真实训练前置检查会
直接失败并误导用户。改为由部署流程（deploy/notebook/download_models.sh）
真实下载模型，再由本服务扫描目录并录入数据库（幂等，可安全重启）。
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.model import Model, ModelVersion, ModelFile
from app.models.user import User


def _uuid() -> str:
    return uuid.uuid4().hex


# 扩展名 → 文件类型（与模型文件上传的 file_type 取值保持一致）
_EXT_TYPE: Dict[str, str] = {
    ".safetensors": "safetensors",
    ".bin": "bin",
    ".json": "json",
    ".txt": "txt",
    ".model": "model",
    ".gguf": "gguf",
    ".pt": "pt",
    ".pth": "pth",
    ".ckpt": "ckpt",
    ".onnx": "onnx",
    ".md": "md",
}


def _file_type(name: str) -> str:
    ext = Path(name).suffix.lower()
    return _EXT_TYPE.get(ext, "other")


class ModelSeedService:
    """模型初始化服务：扫描本地已下载的默认模型并录入数据库（幂等）"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def seed(self) -> int:
        """录入默认模型，返回本次插入的模型数量（幂等）。

        当配置了 SEED_MODEL_ID（如 Qwen/Qwen2.5-0.5B-Instruct）且对应模型已
        下载到 backend/workspace/models/<模型名小写>/ 时，将其录入模型库；
        未配置 / 目录不存在或为空 / 已录入过 时跳过（部署脚本负责下载）。
        """
        hub_id = (settings.SEED_MODEL_ID or "").strip().strip('"')
        if not hub_id:
            print("[INFO] Model seed: SEED_MODEL_ID 未配置，跳过默认模型录入")
            return 0

        name = hub_id.rsplit("/", 1)[-1]
        rel_dir = f"models/{name.lower()}"
        abs_dir = self._resolve_workspace_dir(rel_dir)
        if abs_dir is None or not abs_dir.is_dir():
            print(
                f"[INFO] Model seed: 模型目录不存在（{abs_dir}），跳过录入。"
                f"请先下载：bash deploy/notebook/download_models.sh --model {hub_id}"
            )
            return 0

        files = self._scan_files(abs_dir)
        if not files:
            print(f"[INFO] Model seed: 模型目录为空（{abs_dir}），跳过录入")
            return 0

        # 幂等：已按 storage_path 录入过的模型跳过
        existing = await self.db.execute(
            select(Model.id).where(Model.storage_path == str(abs_dir)).limit(1)
        )
        if existing.scalar_one_or_none():
            print(f"[INFO] Model seed: 模型已录入（{name}，{abs_dir}），跳过")
            return 0

        # 所有者：优先 admin 用户（与旧种子逻辑一致）
        result = await self.db.execute(
            select(User).where(User.username == "admin").limit(1)
        )
        admin = result.scalar_one_or_none()
        owner_id = admin.id if admin else None

        model_id = _uuid()
        version_id = _uuid()
        total_size = sum(f["size"] for f in files)

        self.db.add(Model(
            id=model_id,
            name=name,
            type=settings.SEED_MODEL_TYPE,
            spec=settings.SEED_MODEL_SPEC,
            vendor=settings.SEED_MODEL_VENDOR,
            version="v1.0",
            description=f"部署时自动录入的默认模型（{hub_id}），由 ModelScope 下载",
            tags='["默认模型"]',
            icon_url="",
            storage_path=str(abs_dir),
            is_public=True,
            owner_id=owner_id,
            status="active",
        ))
        self.db.add(ModelVersion(
            id=version_id,
            model_id=model_id,
            version="v1.0",
            description="部署时自动录入的默认版本",
            storage_path=str(abs_dir),
            framework="vLLM",
            size=total_size,
            file_count=len(files),
            status="ready",
            is_default=True,
        ))
        for f in files:
            self.db.add(ModelFile(
                id=_uuid(),
                version_id=version_id,
                file_name=f["name"],
                file_path=f["path"],
                file_size=f["size"],
                file_type=f["type"],
                status="ready",
            ))
        await self.db.flush()
        print(f"[INFO] Model seed: 已录入默认模型 {name}（{len(files)} 个文件，"
              f"共 {total_size / 1024 / 1024 / 1024:.2f} GB）")
        return 1

    def _resolve_workspace_dir(self, rel_dir: str) -> Optional[Path]:
        """解析训练工作目录下的相对路径（兼容绝对路径形式的 TRAIN_WORKSPACE）"""
        ws = (settings.TRAIN_WORKSPACE or "workspace").strip()
        if os.path.isabs(ws):
            return Path(ws) / rel_dir
        backend_dir = Path(__file__).resolve().parent.parent.parent  # backend/
        return backend_dir / ws / rel_dir

    def _scan_files(self, abs_dir: Path) -> List[Dict]:
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
