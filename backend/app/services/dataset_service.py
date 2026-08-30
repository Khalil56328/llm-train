"""数据集服务"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import (
    copy_object,
    delete_object,
    delete_prefix,
    iter_object_chunks,
    move_object,
    version_dir,
    version_key,
)
from app.models.dataset import Dataset, DatasetVersion, DatasetFile
from app.models.user import User

# 北京时区
_BJ = ZoneInfo("Asia/Shanghai")


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    """返回 UTC 时间（naive），与 MySQL 服务器 UTC 时区保持一致"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fmt_time(dt: Optional[datetime]) -> Optional[str]:
    """naive datetime 视为 UTC，转换为北京时间（+08:00）ISO 字符串"""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_BJ).isoformat()


def _dir_of(storage_path: str) -> str:
    """返回 storage_path 所在目录（作为训练引擎的 --dataset 输入）。

    - 本地绝对路径：取父目录（swift 通常按目录扫描数据文件）
    - minio:// 路径：取对象 key 的目录部分，去掉 bucket 前缀，保留统一前缀
    """
    if storage_path.startswith("minio://"):
        bucket_key = storage_path[len("minio://"):]
        _, _, key = bucket_key.partition("/")
        idx = key.rfind("/")
        return f"minio://{bucket_key[: bucket_key.rfind('/')]}" if idx >= 0 else storage_path
    p = Path(storage_path)
    return str(p.parent if p.suffix else p)


def _is_legacy_file_path(storage_path: str, dataset_id: str) -> bool:
    """文件是否仍位于数据集级目录（datasets/{dataset_id}/，未按版本组织）。

    历史数据（版本功能上线前）的文件都直接落在数据集级目录下；
    版本目录结构为 datasets/{dataset_id}/versions/{version_id}/...
    """
    if not storage_path:
        return False
    norm = storage_path.replace("\\", "/")
    if f"/datasets/{dataset_id}/" not in norm:
        return False
    return "/versions/" not in norm


class DatasetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_datasets(
        self,
        *,
        page_index: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        data_type: Optional[str] = None,
        status: Optional[str] = None,
        dataset_type: Optional[str] = None,
        owner_id: Optional[str] = None,
        is_public: Optional[bool] = None,
    ) -> Dict:
        q = select(Dataset)
        count_q = select(func.count(Dataset.id))

        if keyword:
            f = Dataset.name.contains(keyword)
            q, count_q = q.where(f), count_q.where(f)
        if category:
            q, count_q = q.where(Dataset.category == category), count_q.where(Dataset.category == category)
        if data_type:
            q, count_q = q.where(Dataset.data_type == data_type), count_q.where(Dataset.data_type == data_type)
        if status:
            q, count_q = q.where(Dataset.status == status), count_q.where(Dataset.status == status)
        if dataset_type:
            q, count_q = q.where(Dataset.type == dataset_type), count_q.where(Dataset.type == dataset_type)
        if owner_id:
            q, count_q = q.where(Dataset.owner_id == owner_id), count_q.where(Dataset.owner_id == owner_id)
        if is_public is not None:
            q, count_q = q.where(Dataset.is_public == is_public), count_q.where(Dataset.is_public == is_public)

        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(Dataset.created_at.desc())
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()

        # 批量统计文件数量，避免 N+1
        file_counts = {}
        version_stats = {}
        if rows:
            ids = [d.id for d in rows]
            cnt_result = await self.db.execute(
                select(DatasetFile.dataset_id, func.count(DatasetFile.id), func.sum(DatasetFile.size))
                .where(DatasetFile.dataset_id.in_(ids), DatasetFile.status == "success")
                .group_by(DatasetFile.dataset_id)
            )
            for dataset_id, count, size in cnt_result.all():
                file_counts[dataset_id] = {"fileCount": count, "totalSize": size or 0}

            # 批量统计版本数与默认版本号
            v_cnt = await self.db.execute(
                select(DatasetVersion.dataset_id, func.count(DatasetVersion.id))
                .where(DatasetVersion.dataset_id.in_(ids))
                .group_by(DatasetVersion.dataset_id)
            )
            for dataset_id, cnt in v_cnt.all():
                version_stats.setdefault(dataset_id, {})["versionCount"] = cnt
            v_def = await self.db.execute(
                select(DatasetVersion.dataset_id, DatasetVersion.version)
                .where(DatasetVersion.dataset_id.in_(ids), DatasetVersion.is_default.is_(True))
            )
            for dataset_id, ver in v_def.all():
                version_stats.setdefault(dataset_id, {})["defaultVersion"] = ver

        # 批量解析归属用户显示名，避免 N+1
        owner_map = await self._resolve_owner_names(
            [d.owner_id for d in rows if d.owner_id]
        )

        return {
            "list": [
                self._dataset_with_files(
                    d, file_counts,
                    owner_name=owner_map.get(d.owner_id or ""),
                    version_stats=version_stats.get(d.id, {}),
                )
                for d in rows
            ],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    def _dataset_with_files(
        self,
        d: Dataset,
        file_counts: Dict,
        owner_name: Optional[str] = None,
        version_stats: Optional[Dict] = None,
    ) -> Dict:
        result = _dataset_to_dict(d, owner_name=owner_name)
        stats = file_counts.get(d.id, {})
        result["fileCount"] = stats.get("fileCount", 0)
        if stats.get("totalSize"):
            result["size"] = stats["totalSize"]
        vs = version_stats or {}
        result["versionCount"] = vs.get("versionCount", 0)
        result["defaultVersion"] = vs.get("defaultVersion")
        return result

    async def get_dataset(self, dataset_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        d = result.scalar_one_or_none()
        if not d:
            return None
        owner_map = await self._resolve_owner_names([d.owner_id] if d.owner_id else [])
        r = _dataset_to_dict(d, owner_name=owner_map.get(d.owner_id or ""))
        # 附加文件统计
        fc = (await self.db.execute(
            select(func.count(DatasetFile.id))
            .where(DatasetFile.dataset_id == dataset_id, DatasetFile.status == "success")
        )).scalar() or 0
        fs = (await self.db.execute(
            select(func.sum(DatasetFile.size))
            .where(DatasetFile.dataset_id == dataset_id, DatasetFile.status == "success")
        )).scalar() or 0
        r["fileCount"] = fc
        r["size"] = fs
        # 附加版本统计
        r["versionCount"] = (await self.db.execute(
            select(func.count(DatasetVersion.id)).where(DatasetVersion.dataset_id == dataset_id)
        )).scalar() or 0
        dv = (await self.db.execute(
            select(DatasetVersion.version).where(
                DatasetVersion.dataset_id == dataset_id,
                DatasetVersion.is_default.is_(True),
            ).limit(1)
        )).scalar()
        r["defaultVersion"] = dv
        return r

    async def create_dataset(self, data: Dict, *, owner_id: str, owner_name: Optional[str] = None) -> Dict:
        d = Dataset(
            id=_uuid(),
            name=data.get("name"),
            category=data.get("category"),
            type=data.get("type", "training"),
            data_type=data.get("data_type"),
            eval_dimensions=data.get("eval_dimensions"),
            description=data.get("description"),
            source=data.get("source", "upload"),
            storage_path=data.get("storage_path"),
            size=data.get("size", 0),
            sample_count=data.get("sample_count", 0),
            is_public=data.get("is_public", False),
            owner_id=owner_id,
            status=data.get("status", "ready"),
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(d)
        # 自动创建初始版本 v1 并设为默认；每个版本拥有独立存储目录，
        # 文件真正落在 versions/{version_id}/ 下
        v1_id = _uuid()
        v1_storage = data.get("storage_path") or version_dir(d.id, v1_id)
        if not d.storage_path:
            d.storage_path = v1_storage
        v1 = DatasetVersion(
            id=v1_id,
            dataset_id=d.id,
            version="v1",
            description=data.get("description"),
            storage_path=v1_storage,
            is_default=True,
            created_by=owner_name or owner_id,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(v1)
        await self.db.flush()
        await self.db.refresh(d)
        r = _dataset_to_dict(d, owner_name=owner_name)
        r["versionCount"] = 1
        r["defaultVersion"] = "v1"
        return r

    async def update_dataset(self, dataset_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        d = result.scalar_one_or_none()
        if not d:
            return None
        _ALLOWED = {"name", "category", "data_type", "eval_dimensions", "description",
                     "source", "storage_path", "is_public", "status"}
        for k, v in data.items():
            if k in _ALLOWED and v is not None:
                setattr(d, k, v)
        d.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(d)
        return _dataset_to_dict(d)

    async def delete_dataset(self, dataset_id: str) -> bool:
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        d = result.scalar_one_or_none()
        if not d:
            return False
        await self.db.execute(delete(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id))
        await self.db.delete(d)
        await self.db.flush()
        return True

    # ========== 版本 ==========
    async def list_versions(self, dataset_id: str) -> List[Dict]:
        await self._migrate_legacy_files(dataset_id)
        result = await self.db.execute(
            select(DatasetVersion).where(DatasetVersion.dataset_id == dataset_id)
                .order_by(DatasetVersion.created_at.desc())
        )
        return [_version_to_dict(v) for v in result.scalars().all()]

    async def get_version(self, dataset_id: str, version_id: str) -> Optional[Dict]:
        result = await self.db.execute(
            select(DatasetVersion).where(
                DatasetVersion.id == version_id,
                DatasetVersion.dataset_id == dataset_id,
            )
        )
        v = result.scalar_one_or_none()
        return _version_to_dict(v) if v else None

    async def _next_version_number(self, dataset_id: str) -> str:
        """解析现有 vN 版本号，返回下一个版本号（v1、v2...）"""
        rows = (await self.db.execute(
            select(DatasetVersion.version).where(DatasetVersion.dataset_id == dataset_id)
        )).scalars().all()
        max_num = 0
        for ver in rows:
            if ver and ver.startswith("v"):
                try:
                    max_num = max(max_num, int(ver[1:]))
                except ValueError:
                    continue
        return f"v{max_num + 1}"

    async def _get_default_version(self, dataset_id: str) -> Optional[DatasetVersion]:
        result = await self.db.execute(
            select(DatasetVersion).where(
                DatasetVersion.dataset_id == dataset_id,
                DatasetVersion.is_default.is_(True),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _mark_default(self, dataset_id: str, version_id: str) -> None:
        await self.db.execute(
            update(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .values(is_default=False)
        )
        await self.db.execute(
            update(DatasetVersion)
            .where(DatasetVersion.id == version_id)
            .values(is_default=True, updated_at=_now())
        )

    async def _migrate_legacy_files(self, dataset_id: str) -> int:
        """历史兼容：将未挂版本 / 未按版本目录落盘的旧文件迁移到默认版本。

        版本功能上线前的文件 version_id 为空；其中物理文件落在数据集级目录
        （datasets/{dataset_id}/...）的，同时移动到所属版本目录。
        演示数据集文件位于共享目录（workspace/datasets/demo1/...，路径不含
        dataset_id），只补版本归属，不移动物理文件。
        迁移后：
        1. version_id 为空 → 挂到默认版本
        2. 物理文件仍在数据集级目录 → 移动到所属版本目录
        """
        default_v = await self._get_default_version(dataset_id)
        if not default_v:
            return 0
        rows = (await self.db.execute(
            select(DatasetFile).where(
                DatasetFile.dataset_id == dataset_id,
                DatasetFile.status == "success",
            )
        )).scalars().all()
        if not rows:
            return 0
        versions: Dict[str, DatasetVersion] = {}
        moved = changed = 0
        for f in rows:
            old = f.storage_path or ""
            legacy_path = _is_legacy_file_path(old, dataset_id)
            # 1) 未挂版本的文件（历史数据 / 老演示数据集）挂到默认版本
            if not f.version_id:
                f.version_id = default_v.id
                changed += 1
            # 2) 物理文件仍在数据集级目录 → 移动到所属版本目录
            if not legacy_path:
                continue
            v = versions.get(f.version_id)
            if v is None:
                v = (await self.db.execute(
                    select(DatasetVersion).where(DatasetVersion.id == f.version_id)
                )).scalar_one_or_none()
                versions[f.version_id] = v
            if v is None:
                continue
            new_path = move_object(old, version_key(dataset_id, f.version_id))
            if new_path != old:
                f.storage_path = new_path
                moved += 1
        if changed or moved:
            await self.db.flush()
            for vid in versions:
                if vid:
                    await self._recount_version_stats(vid)
        return moved

    async def create_version(
        self,
        dataset_id: str,
        data: Dict,
        *,
        created_by: Optional[str] = None,
    ) -> Optional[Dict]:
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        ds = result.scalar_one_or_none()
        if not ds:
            return None

        version = (data.get("version") or "").strip()
        if not version:
            version = await self._next_version_number(dataset_id)

        dup = (await self.db.execute(
            select(func.count(DatasetVersion.id)).where(
                DatasetVersion.dataset_id == dataset_id,
                DatasetVersion.version == version,
            )
        )).scalar()
        if dup:
            raise ValueError(f"版本号 {version} 已存在")

        v_id = _uuid()
        v = DatasetVersion(
            id=v_id,
            dataset_id=dataset_id,
            version=version,
            description=data.get("description"),
            storage_path=data.get("storage_path") or version_dir(dataset_id, v_id),
            is_default=False,
            created_by=created_by,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(v)
        await self.db.flush()

        # 无默认版本（首个版本）或请求指定默认时，切换默认版本
        default_v = await self._get_default_version(dataset_id)
        if data.get("is_default") or default_v is None:
            await self._mark_default(dataset_id, v.id)

        await self.db.refresh(v)
        return _version_to_dict(v)

    async def update_version(self, dataset_id: str, version_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(
            select(DatasetVersion).where(
                DatasetVersion.id == version_id,
                DatasetVersion.dataset_id == dataset_id,
            )
        )
        v = result.scalar_one_or_none()
        if not v:
            return None

        new_version = (data.get("version") or "").strip()
        if new_version and new_version != v.version:
            dup = (await self.db.execute(
                select(func.count(DatasetVersion.id)).where(
                    DatasetVersion.dataset_id == dataset_id,
                    DatasetVersion.version == new_version,
                    DatasetVersion.id != version_id,
                )
            )).scalar()
            if dup:
                raise ValueError(f"版本号 {new_version} 已存在")
            v.version = new_version

        if "description" in data:
            v.description = data.get("description")
        if data.get("is_default") is True:
            await self._mark_default(dataset_id, version_id)
            await self.db.refresh(v)

        v.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(v)
        return _version_to_dict(v)

    async def set_default_version(self, dataset_id: str, version_id: str) -> Optional[Dict]:
        result = await self.db.execute(
            select(DatasetVersion).where(
                DatasetVersion.id == version_id,
                DatasetVersion.dataset_id == dataset_id,
            )
        )
        v = result.scalar_one_or_none()
        if not v:
            return None
        await self._mark_default(dataset_id, version_id)
        await self.db.refresh(v)
        return _version_to_dict(v)

    async def delete_version(self, dataset_id: str, version_id: str) -> bool:
        result = await self.db.execute(
            select(DatasetVersion).where(
                DatasetVersion.id == version_id,
                DatasetVersion.dataset_id == dataset_id,
            )
        )
        v = result.scalar_one_or_none()
        if not v:
            return False

        cnt = (await self.db.execute(
            select(func.count(DatasetVersion.id)).where(DatasetVersion.dataset_id == dataset_id)
        )).scalar() or 0
        if cnt <= 1:
            raise ValueError("至少保留一个版本，无法删除")

        was_default = bool(v.is_default)

        # 删除版本目录下所有物理对象（含未登记文件），再删除文件记录
        delete_prefix(version_key(dataset_id, version_id))
        files = (await self.db.execute(
            select(DatasetFile).where(DatasetFile.version_id == version_id)
        )).scalars().all()
        for f in files:
            if f.storage_path:
                delete_object(f.storage_path)
        await self.db.execute(delete(DatasetFile).where(DatasetFile.version_id == version_id))

        await self.db.delete(v)
        await self.db.flush()

        # 默认版本被删后，转移到最新的剩余版本
        if was_default:
            latest = (await self.db.execute(
                select(DatasetVersion)
                .where(DatasetVersion.dataset_id == dataset_id)
                .order_by(DatasetVersion.created_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            if latest:
                await self._mark_default(dataset_id, latest.id)

        await self._sync_dataset_size(dataset_id)
        return True

    # ========== 文件 ==========
    async def list_files(
        self,
        dataset_id: str,
        *,
        page_index: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        version_id: Optional[str] = None,
    ) -> Dict:
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        if not result.scalar_one_or_none():
            return None

        await self._migrate_legacy_files(dataset_id)
        q = select(DatasetFile).where(DatasetFile.dataset_id == dataset_id)
        count_q = select(func.count(DatasetFile.id)).where(DatasetFile.dataset_id == dataset_id)

        if version_id:
            f = DatasetFile.version_id == version_id
            q, count_q = q.where(f), count_q.where(f)
        if keyword:
            f = DatasetFile.file_name.contains(keyword)
            q, count_q = q.where(f), count_q.where(f)
        if status:
            q, count_q = q.where(DatasetFile.status == status), count_q.where(DatasetFile.status == status)

        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(DatasetFile.created_at.desc())
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()

        return {
            "list": [_file_to_dict(f) for f in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def get_file_stats(self, dataset_id: str, *, version_id: Optional[str] = None) -> Dict:
        """获取数据集文件统计信息（可按版本过滤）"""
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        if not result.scalar_one_or_none():
            return None

        def _scope():
            conds = [DatasetFile.dataset_id == dataset_id]
            if version_id:
                conds.append(DatasetFile.version_id == version_id)
            return conds

        conds = _scope()
        total = (await self.db.execute(
            select(func.count(DatasetFile.id)).where(*conds)
        )).scalar() or 0
        success = (await self.db.execute(
            select(func.count(DatasetFile.id)).where(*conds, DatasetFile.status == "success")
        )).scalar() or 0
        failed = (await self.db.execute(
            select(func.count(DatasetFile.id)).where(*conds, DatasetFile.status == "failed")
        )).scalar() or 0
        processing = (await self.db.execute(
            select(func.count(DatasetFile.id)).where(*conds, DatasetFile.status == "processing")
        )).scalar() or 0
        total_size = (await self.db.execute(
            select(func.sum(DatasetFile.size)).where(*conds, DatasetFile.status == "success")
        )).scalar() or 0
        return {
            "fileCount": total,
            "success": success,
            "failed": failed,
            "processing": processing,
            "totalSize": total_size,
        }

    async def create_file(self, dataset_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        ds = result.scalar_one_or_none()
        if not ds:
            return None

        # 解析目标版本：显式指定 version_id，否则挂到默认版本
        version_id = data.get("version_id")
        if version_id:
            v_exists = (await self.db.execute(
                select(func.count(DatasetVersion.id)).where(
                    DatasetVersion.id == version_id,
                    DatasetVersion.dataset_id == dataset_id,
                )
            )).scalar()
            if not v_exists:
                raise ValueError("目标版本不存在")
        else:
            dv = await self._get_default_version(dataset_id)
            version_id = dv.id if dv else None

        f = DatasetFile(
            id=_uuid(),
            dataset_id=dataset_id,
            version_id=version_id,
            file_name=data.get("file_name"),
            source=data.get("source", "local_upload"),
            status=data.get("status", "processing"),
            size=data.get("size", 0),
            storage_path=data.get("storage_path"),
            batch_id=data.get("batch_id"),
            sample_count=data.get("sample_count", 0),
            error_message=data.get("error_message"),
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(f)
        await self.db.flush()
        await self.db.refresh(f)
        await self._sync_dataset_size(dataset_id)
        if f.version_id:
            await self._recount_version_stats(f.version_id)
            # 版本存储路径缺失时（历史数据），用版本目录补齐
            if f.status == "success":
                v_result = await self.db.execute(
                    select(DatasetVersion).where(DatasetVersion.id == f.version_id)
                )
                v = v_result.scalar_one_or_none()
                if v and not v.storage_path:
                    v.storage_path = version_dir(dataset_id, f.version_id)
                    v.updated_at = _now()
                    await self.db.flush()
        # 顶层数据集 storage_path 为空时，指向默认版本目录，供训练 executor 回退使用。
        # 使上传数据集与平台初始化数据集一样可直接用于真实训练。
        if f.status == "success" and not ds.storage_path and f.version_id:
            ds.storage_path = version_dir(dataset_id, f.version_id)
            ds.updated_at = _now()
            await self.db.flush()
        return _file_to_dict(f)

    async def get_file(self, file_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(DatasetFile).where(DatasetFile.id == file_id))
        f = result.scalar_one_or_none()
        return _file_to_dict(f) if f else None

    async def delete_file(self, file_id: str) -> bool:
        result = await self.db.execute(select(DatasetFile).where(DatasetFile.id == file_id))
        f = result.scalar_one_or_none()
        if not f:
            return False
        dataset_id = f.dataset_id
        version_id = f.version_id
        storage_path = f.storage_path
        await self.db.delete(f)
        await self.db.flush()
        await self._sync_dataset_size(dataset_id)
        if version_id:
            await self._recount_version_stats(version_id)
        # 同步删除物理文件
        if storage_path:
            delete_object(storage_path)
        return True

    async def list_collect_tasks(
        self,
        dataset_id: str,
        *,
        version_id: Optional[str] = None,
    ) -> Optional[List[Dict]]:
        """采集任务：按批次(batch_id)聚合。

        任务名 = 批次上传时间；状态 = 批次内所有文件聚合
        （任一失败则 failed，任一处理中则 processing，否则 success）；
        采集方式 = 该批次文件的数据来源(source)。
        """
        result = await self.db.execute(select(Dataset).where(Dataset.id == dataset_id))
        if not result.scalar_one_or_none():
            return None

        conds = [DatasetFile.dataset_id == dataset_id, DatasetFile.batch_id.isnot(None)]
        if version_id:
            conds.append(DatasetFile.version_id == version_id)
        rows = (await self.db.execute(
            select(DatasetFile)
            .where(*conds)
            .order_by(DatasetFile.created_at.desc())
        )).scalars().all()

        groups: Dict[str, List[DatasetFile]] = {}
        for f in rows:
            groups.setdefault(f.batch_id, []).append(f)

        tasks = []
        for batch_id, files in groups.items():
            files_sorted = sorted(files, key=lambda x: x.created_at or _now())
            status = "success"
            if any(f.status == "failed" for f in files):
                status = "failed"
            elif any(f.status == "processing" for f in files):
                status = "processing"
            tasks.append({
                "batchId": batch_id,
                "taskName": _fmt_time(files_sorted[0].created_at),
                "source": files_sorted[0].source,
                "status": status,
                "fileCount": len(files),
                "successCount": sum(1 for f in files if f.status == "success"),
                "failedCount": sum(1 for f in files if f.status == "failed"),
            })
        return tasks

    @staticmethod
    def count_file_rows(storage_path: str, file_name: str) -> int:
        """结合 MS-Swift 支持的数据集格式统计样本行数。

        - jsonl/json: 每行一条样本
        - csv: 行数减表头
        - txt: 非空行数
        - 其余格式（parquet/zip 等）无法按行统计，返回 0
        """
        ext = Path(file_name).suffix.lower()
        if ext not in (".jsonl", ".json", ".csv", ".txt"):
            return 0

        newlines = 0
        last_chunk = b""
        empty = True
        for chunk in iter_object_chunks(storage_path):
            newlines += chunk.count(b"\n")
            last_chunk = chunk
            if chunk.strip():
                empty = False

        if empty:
            return 0

        # 文件末尾无换行符时补计一行
        if not last_chunk.endswith(b"\n"):
            newlines += 1

        if ext == ".csv":
            # 去掉表头行
            return max(newlines - 1, 0)
        return newlines

    async def copy_files(self, source_id: str, target_id: str) -> int:
        result = await self.db.execute(select(DatasetFile).where(DatasetFile.dataset_id == source_id))
        rows = result.scalars().all()
        # 复制到目标数据集的默认版本，物理文件也复制到目标版本目录
        dv = await self._get_default_version(target_id)
        target_vid = dv.id if dv else None
        target_sub = version_key(target_id, target_vid) if target_vid else f"datasets/{target_id}"
        for f in rows:
            new_path = f.storage_path
            if f.storage_path and f.status == "success":
                new_path = copy_object(f.storage_path, target_sub)
            self.db.add(DatasetFile(
                id=_uuid(),
                dataset_id=target_id,
                version_id=target_vid,
                file_name=f.file_name,
                source=f.source,
                status=f.status,
                size=f.size,
                storage_path=new_path,
                batch_id=None,
                sample_count=f.sample_count,
                error_message=f.error_message,
                created_at=_now(),
                updated_at=_now(),
            ))
        await self.db.flush()
        await self._sync_dataset_size(target_id)
        if target_vid:
            await self._recount_version_stats(target_vid)
        return len(rows)

    async def _resolve_owner_names(self, owner_ids: List[str]) -> Dict[str, str]:
        """根据用户 ID 批量解析显示名（昵称优先，回退用户名）"""
        if not owner_ids:
            return {}
        result = await self.db.execute(
            select(User.id, User.nickname, User.username).where(
                User.id.in_(owner_ids)
            )
        )
        return {
            uid: (nickname or username or uid)
            for uid, nickname, username in result.all()
        }

    async def _sync_dataset_size(self, dataset_id: str) -> None:
        total_size = (await self.db.execute(
            select(func.sum(DatasetFile.size)).where(
                DatasetFile.dataset_id == dataset_id,
                DatasetFile.status == "success",
            )
        )).scalar() or 0
        # 样本数 = 成功文件的样本行数总和（而非文件个数）
        sample_count = (await self.db.execute(
            select(func.sum(DatasetFile.sample_count)).where(
                DatasetFile.dataset_id == dataset_id,
                DatasetFile.status == "success",
            )
        )).scalar() or 0
        await self.db.execute(
            update(Dataset)
            .where(Dataset.id == dataset_id)
            .values(size=total_size, sample_count=sample_count)
        )

    async def _recount_version_stats(self, version_id: str) -> None:
        """按版本聚合成功文件的数量/大小/样本数，回写版本表"""
        file_count = (await self.db.execute(
            select(func.count(DatasetFile.id)).where(
                DatasetFile.version_id == version_id,
                DatasetFile.status == "success",
            )
        )).scalar() or 0
        total_size = (await self.db.execute(
            select(func.sum(DatasetFile.size)).where(
                DatasetFile.version_id == version_id,
                DatasetFile.status == "success",
            )
        )).scalar() or 0
        sample_count = (await self.db.execute(
            select(func.sum(DatasetFile.sample_count)).where(
                DatasetFile.version_id == version_id,
                DatasetFile.status == "success",
            )
        )).scalar() or 0
        await self.db.execute(
            update(DatasetVersion)
            .where(DatasetVersion.id == version_id)
            .values(
                file_count=file_count,
                size=total_size,
                sample_count=sample_count,
                updated_at=_now(),
            )
        )


def _dataset_to_dict(d: Dataset, owner_name: Optional[str] = None) -> Dict:
    return {
        "id": d.id,
        "name": d.name,
        "category": d.category,
        "type": d.type,
        "dataType": d.data_type,
        "evalDimensions": d.eval_dimensions,
        "description": d.description,
        "source": d.source,
        "storagePath": d.storage_path,
        "size": d.size,
        "sampleCount": d.sample_count,
        "isPublic": d.is_public,
        "ownerId": d.owner_id,
        "ownerName": owner_name,
        "status": d.status,
        "createdAt": _fmt_time(d.created_at),
        "updatedAt": _fmt_time(d.updated_at),
    }


def _version_to_dict(v: DatasetVersion) -> Dict:
    return {
        "id": v.id,
        "datasetId": v.dataset_id,
        "version": v.version,
        "description": v.description,
        "storagePath": v.storage_path,
        "fileCount": v.file_count or 0,
        "size": v.size or 0,
        "sampleCount": v.sample_count or 0,
        "isDefault": v.is_default,
        "createdBy": v.created_by,
        "createdAt": _fmt_time(v.created_at),
        "updatedAt": _fmt_time(v.updated_at),
    }


def _file_to_dict(f: DatasetFile) -> Dict:
    return {
        "id": f.id,
        "datasetId": f.dataset_id,
        "versionId": f.version_id,
        "fileName": f.file_name,
        "source": f.source,
        "status": f.status,
        "size": f.size,
        "storagePath": f.storage_path,
        "batchId": f.batch_id,
        "sampleCount": f.sample_count,
        "errorMessage": f.error_message,
        "createdAt": _fmt_time(f.created_at),
        "updatedAt": _fmt_time(f.updated_at),
    }
