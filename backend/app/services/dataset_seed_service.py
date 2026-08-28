"""演示数据集初始化服务

把部署脚本（deploy/common/seed_demo_data.py）生成的演示数据集录入数据库
（datasets / dataset_versions / dataset_files 三张表），使训练向导开箱可选。

每个演示数据集目录要求包含 dataset.json 元信息，示例：
{
  "name": "self-cognition 演示SFT数据集",
  "type": "training",            # training / evaluation
  "data_type": "SFT",            # SFT / DPO / CPT / general ...
  "description": "用于微调演示的对话数据集",
  "sample_count": 100
}

幂等：已按 storage_path 录入过的数据集跳过，可安全重启。
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.dataset import Dataset, DatasetVersion, DatasetFile
from app.models.user import User


def _uuid() -> str:
    return uuid.uuid4().hex


# 视为数据文件的扩展名（dataset.json 为目录元信息，不算数据文件）
_DATA_FILE_EXTS = {".jsonl", ".json", ".csv", ".txt", ".parquet"}


def _has_data_files(abs_dir: Path) -> bool:
    """目录内是否至少包含一个真实数据文件（非 dataset.json、非隐藏文件）"""
    try:
        for f in abs_dir.iterdir():
            if not f.is_file() or f.name.startswith(".") or f.name == "dataset.json":
                continue
            if f.suffix.lower() in _DATA_FILE_EXTS:
                return True
    except OSError:
        pass
    return False


class DatasetSeedService:
    """扫描 workspace/datasets/ 下带 dataset.json 的演示数据集并录入（幂等）"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def seed(self) -> int:
        """录入演示数据集，返回本次插入的数量（幂等）"""
        root = self._resolve_workspace_dir("datasets")
        # 启动自愈：补齐缺失的演示数据集文件（SFT / 偏好 / 预训练），
        # 不再单纯依赖部署脚本 seed_demo_data.py 的一次性生成
        try:
            from app.services.demo_dataset_generator import ensure_demo_datasets
            generated = ensure_demo_datasets(root)
            if generated:
                print(f"[INFO] Dataset seed: 已生成/补齐演示数据集文件 {generated}")
        except Exception as e:
            print(f"[WARN] Demo dataset generation failed: {e}")
        if root is None or not root.is_dir():
            return 0
        inserted = 0
        for meta_path in sorted(root.glob("*/dataset.json")):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(meta, dict) or not meta.get("name"):
                continue
            abs_dir = meta_path.parent
            # 校验目录内确实存在数据文件，避免录入"只有元信息没有数据文件"的脏记录
            if not _has_data_files(abs_dir):
                print(f"[WARN] Dataset seed: 跳过无数据文件的目录 {abs_dir}")
                continue
            # 幂等：已按 storage_path 录入过的数据集跳过
            existing = await self.db.execute(
                select(Dataset.id).where(Dataset.storage_path == str(abs_dir)).limit(1)
            )
            if existing.scalar_one_or_none():
                continue
            if await self._insert_one(abs_dir, meta):
                inserted += 1
        if inserted:
            await self.db.flush()
        return inserted

    async def _insert_one(self, abs_dir: Path, meta: Dict) -> bool:
        result = await self.db.execute(
            select(User).where(User.username == "admin").limit(1)
        )
        admin = result.scalar_one_or_none()
        owner_id = admin.id if admin else "system"

        name = str(meta["name"]).strip()[:200]
        data_type = str(meta.get("data_type") or "general").upper()[:20]
        dset = Dataset(
            id=_uuid(),
            name=name,
            category=str(meta.get("category") or "")[:100] or None,
            type=str(meta.get("type") or "training")[:20],
            data_type=data_type,
            description=str(meta.get("description") or "")[:500] or None,
            source="platform",
            storage_path=str(abs_dir),
            size=0,
            sample_count=int(meta.get("sample_count") or 0),
            is_public=True,
            owner_id=owner_id,
            status="ready",
        )
        self.db.add(dset)
        await self.db.flush()

        self.db.add(DatasetVersion(
            id=_uuid(),
            dataset_id=dset.id,
            version="v1",
            storage_path=str(abs_dir),
            is_default=True,
        ))

        total_size = 0
        for f in sorted(abs_dir.iterdir()):
            if not f.is_file() or f.name == "dataset.json" or f.name.startswith("."):
                continue
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            total_size += size
            self.db.add(DatasetFile(
                id=_uuid(),
                dataset_id=dset.id,
                file_name=f.name,
                source="platform",
                status="success",
                size=size,
                storage_path=str(f),
                sample_count=0,
            ))
        dset.size = total_size
        print(f"[INFO] Dataset seed: 已录入演示数据集 {name}（{dset.storage_path}）")
        return True

    def _resolve_workspace_dir(self, rel_dir: str) -> Optional[Path]:
        """解析训练工作目录下的相对路径（兼容绝对路径形式的 TRAIN_WORKSPACE）"""
        ws = (settings.TRAIN_WORKSPACE or "workspace").strip()
        if os.path.isabs(ws):
            return Path(ws) / rel_dir
        backend_dir = Path(__file__).resolve().parent.parent.parent  # backend/
        return backend_dir / ws / rel_dir
