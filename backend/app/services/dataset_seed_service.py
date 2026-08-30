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
from datetime import datetime
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


def _estimate_file_samples(p: Path) -> int:
    """粗略统计数据文件样本数：jsonl/txt 每行一条，csv 减表头，其他格式返回 0"""
    suffix = p.suffix.lower()
    if suffix not in (".jsonl", ".csv", ".txt"):
        return 0
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as fh:
            count = sum(1 for _ in fh)
        return max(count - 1, 0) if suffix == ".csv" else count
    except OSError:
        return 0


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
            # 幂等：已按 storage_path 录入过的数据集跳过，但老数据需要自愈
            # （版本统计/创建人为空、文件未挂版本/样本数为 0）
            existing = await self.db.execute(
                select(Dataset.id).where(Dataset.storage_path == str(abs_dir)).limit(1)
            )
            existing_id = existing.scalar_one_or_none()
            if existing_id:
                if await self._heal_version(existing_id, abs_dir, meta):
                    await self.db.flush()
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
        eval_dimensions = meta.get("eval_dimensions")
        dset = Dataset(
            id=_uuid(),
            name=name,
            category=str(meta.get("category") or "")[:100] or None,
            type=str(meta.get("type") or "training")[:20],
            eval_dimensions=(json.dumps(eval_dimensions, ensure_ascii=False)[:500]
                             if isinstance(eval_dimensions, dict)
                             else (str(eval_dimensions)[:500] if eval_dimensions else None)),
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

        now = datetime.now()
        data_files = [
            f for f in sorted(abs_dir.iterdir())
            if f.is_file() and f.name != "dataset.json" and not f.name.startswith(".")
        ]
        total_size = 0
        for f in data_files:
            try:
                total_size += f.stat().st_size
            except OSError:
                pass

        # 演示数据集目录本身就是 v1 版本目录（文件直接位于该目录下）
        v1_id = _uuid()
        self.db.add(DatasetVersion(
            id=v1_id,
            dataset_id=dset.id,
            version="v1",
            storage_path=str(abs_dir),
            file_count=len(data_files),
            size=total_size,
            sample_count=int(meta.get("sample_count") or 0),
            is_default=True,
            created_by="平台",
            created_at=now,
            updated_at=now,
        ))

        for f in data_files:
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            self.db.add(DatasetFile(
                id=_uuid(),
                dataset_id=dset.id,
                version_id=v1_id,
                file_name=f.name,
                source="platform",
                status="success",
                size=size,
                storage_path=str(f),
                sample_count=_estimate_file_samples(f),
            ))
        dset.size = total_size
        print(f"[INFO] Dataset seed: 已录入演示数据集 {name}（{dset.storage_path}）")
        return True

    async def _heal_version(self, dataset_id: str, abs_dir: Path, meta: Dict) -> bool:
        """自愈：为已录入的演示数据集补齐版本统计/创建人与文件样本数/版本归属。

        老环境录入的演示数据集：版本记录统计为空（file_count=0、created_by 为空、
        sample_count=0），文件也未挂版本（version_id 为空）、样本数为 0。
        这里按目录重新统计补齐，避免版本展开面板显示 0 与 "-"。
        """
        result = await self.db.execute(
            select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
        )
        versions = result.scalars().all()
        if not versions:
            return False
        default_v = next((v for v in versions if v.is_default), versions[0])

        data_files = [
            f for f in sorted(abs_dir.iterdir())
            if f.is_file() and f.name != "dataset.json" and not f.name.startswith(".")
        ]
        total_size = 0
        for f in data_files:
            try:
                total_size += f.stat().st_size
            except OSError:
                pass

        now = datetime.now()
        need_flush = False
        for v in versions:
            if not v.file_count or not v.created_by:
                v.file_count = len(data_files)
                v.size = total_size
                v.sample_count = int(meta.get("sample_count") or 0)
                v.created_by = v.created_by or "平台"
                v.created_at = v.created_at or now
                v.updated_at = now
                need_flush = True

        # 目录内文件：补齐样本数；未挂版本的文件挂到默认版本
        rows = (await self.db.execute(
            select(DatasetFile).where(DatasetFile.dataset_id == dataset_id)
        )).scalars().all()
        for f in rows:
            if f.sample_count == 0 and f.storage_path:
                p = Path(f.storage_path)
                if p.is_file():
                    f.sample_count = _estimate_file_samples(p)
                    need_flush = True
            if not f.version_id and default_v:
                f.version_id = default_v.id
                need_flush = True
        if need_flush:
            await self.db.flush()
        return need_flush

    def _resolve_workspace_dir(self, rel_dir: str) -> Optional[Path]:
        """解析训练工作目录下的相对路径（兼容绝对路径形式的 TRAIN_WORKSPACE）"""
        ws = (settings.TRAIN_WORKSPACE or "workspace").strip()
        if os.path.isabs(ws):
            return Path(ws) / rel_dir
        backend_dir = Path(__file__).resolve().parent.parent.parent  # backend/
        return backend_dir / ws / rel_dir
