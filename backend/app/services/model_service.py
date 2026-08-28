"""模型库服务"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select, func, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model, ModelVersion, ModelFile


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now()


def _dir_of(storage_path: str) -> str:
    """返回 storage_path 所在目录（作为训练/部署引擎的模型路径输入）。

    - 本地绝对路径：取父目录
    - minio:// 路径：取对象 key 的目录部分，去掉 bucket 前缀，保留统一前缀
    """
    if storage_path.startswith("minio://"):
        bucket_key = storage_path[len("minio://"):]
        idx = bucket_key.rfind("/")
        return f"minio://{bucket_key[:idx]}" if idx >= 0 else storage_path
    p = Path(storage_path)
    return str(p.parent if p.suffix else p)


class ModelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 模型主表 ==========
    async def list_models(
        self,
        *,
        page_index: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        type: Optional[str] = None,
        spec: Optional[str] = None,
        vendor: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        is_public: Optional[bool] = None,
    ) -> Dict:
        q = select(Model)
        count_q = select(func.count(Model.id))

        if keyword:
            f = Model.name.contains(keyword)
            q, count_q = q.where(f), count_q.where(f)
        if type:
            q, count_q = q.where(Model.type == type), count_q.where(Model.type == type)
        if spec:
            q, count_q = q.where(Model.spec == spec), count_q.where(Model.spec == spec)
        if vendor:
            q, count_q = q.where(Model.vendor == vendor), count_q.where(Model.vendor == vendor)
        if status:
            q, count_q = q.where(Model.status == status), count_q.where(Model.status == status)
        if owner_id:
            q, count_q = q.where(Model.owner_id == owner_id), count_q.where(Model.owner_id == owner_id)
        if is_public is not None:
            q, count_q = q.where(Model.is_public == is_public), count_q.where(Model.is_public == is_public)

        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(Model.created_at.desc())
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()

        return {
            "list": [_model_to_dict(m) for m in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def get_model(self, model_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(Model).where(Model.id == model_id))
        m = result.scalar_one_or_none()
        return _model_to_dict(m) if m else None

    async def create_model(self, data: Dict, *, owner_id: str) -> Dict:
        m = Model(
            id=_uuid(),
            name=data.get("name"),
            type=data.get("type"),
            spec=data.get("spec"),
            vendor=data.get("vendor"),
            version=data.get("version", "v1"),
            description=data.get("description"),
            tags=data.get("tags"),
            icon_url=data.get("iconUrl"),
            storage_path=data.get("storagePath"),
            is_public=data.get("isPublic", False),
            owner_id=owner_id,
            status=data.get("status", "active"),
        )
        self.db.add(m)
        await self.db.flush()
        await self.db.refresh(m)
        return _model_to_dict(m)

    async def update_model(self, model_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(Model).where(Model.id == model_id))
        m = result.scalar_one_or_none()
        if not m:
            return None
        field_map = {
            "iconUrl": "icon_url", "storagePath": "storage_path",
            "isPublic": "is_public", "ownerId": "owner_id",
        }
        for k, v in data.items():
            if v is not None:
                setattr(m, field_map.get(k, k), v)
        m.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(m)
        return _model_to_dict(m)

    async def delete_model(self, model_id: str) -> bool:
        result = await self.db.execute(select(Model).where(Model.id == model_id))
        m = result.scalar_one_or_none()
        if not m:
            return False
        # 先删除版本下的文件
        ver_result = await self.db.execute(
            select(ModelVersion.id).where(ModelVersion.model_id == model_id)
        )
        ver_ids = [v for v in ver_result.scalars().all()]
        if ver_ids:
            await self.db.execute(delete(ModelFile).where(ModelFile.version_id.in_(ver_ids)))
        await self.db.execute(delete(ModelVersion).where(ModelVersion.model_id == model_id))
        await self.db.delete(m)
        await self.db.flush()
        return True

    # ========== 广场 ==========
    async def list_plaza_models(
        self,
        *,
        page_index: int = 1,
        page_size: int = 12,
        keyword: Optional[str] = None,
        type: Optional[str] = None,
        spec: Optional[str] = None,
        vendor: Optional[str] = None,
    ) -> Dict:
        return await self.list_models(
            page_index=page_index, page_size=page_size,
            keyword=keyword, type=type, spec=spec, vendor=vendor,
            is_public=True, status="active",
        )

    async def import_model(self, model_id: str, *, owner_id: str) -> Optional[Dict]:
        """将公开模型导入到我的模型库（创建副本）"""
        result = await self.db.execute(select(Model).where(Model.id == model_id))
        src = result.scalar_one_or_none()
        if not src:
            return None
        new_m = Model(
            id=_uuid(),
            name=src.name,
            type=src.type,
            spec=src.spec,
            vendor=src.vendor,
            version=src.version,
            description=src.description,
            tags=src.tags,
            icon_url=src.icon_url,
            storage_path=src.storage_path,
            is_public=False,
            owner_id=owner_id,
            status="active",
        )
        self.db.add(new_m)
        # 复制版本
        ver_result = await self.db.execute(
            select(ModelVersion).where(ModelVersion.model_id == model_id)
        )
        for v in ver_result.scalars().all():
            new_v = ModelVersion(
                id=_uuid(),
                model_id=new_m.id,
                version=v.version,
                description=v.description,
                storage_path=v.storage_path,
                framework=v.framework,
                size=v.size,
                file_count=v.file_count,
                status=v.status,
                is_default=v.is_default,
            )
            self.db.add(new_v)
            # 复制文件
            file_result = await self.db.execute(
                select(ModelFile).where(ModelFile.version_id == v.id)
            )
            for f in file_result.scalars().all():
                new_f = ModelFile(
                    id=_uuid(),
                    version_id=new_v.id,
                    file_name=f.file_name,
                    file_path=f.file_path,
                    file_size=f.file_size,
                    file_type=f.file_type,
                    status=f.status,
                )
                self.db.add(new_f)
        await self.db.flush()
        await self.db.refresh(new_m)
        return _model_to_dict(new_m)

    # ========== 版本 ==========
    async def list_versions(self, model_id: str) -> List[Dict]:
        result = await self.db.execute(
            select(ModelVersion).where(ModelVersion.model_id == model_id)
                .order_by(ModelVersion.created_at.desc())
        )
        return [_mver_to_dict(v) for v in result.scalars().all()]

    async def get_version(self, version_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        v = result.scalar_one_or_none()
        return _mver_to_dict(v) if v else None

    async def create_version(self, model_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(Model).where(Model.id == model_id))
        if not result.scalar_one_or_none():
            return None
        v = ModelVersion(
            id=_uuid(),
            model_id=model_id,
            version=data.get("version", "v1"),
            description=data.get("description"),
            storage_path=data.get("storagePath"),
            framework=data.get("framework"),
            size=data.get("size", 0),
            file_count=data.get("fileCount", 0),
            status=data.get("status", "ready"),
            is_default=data.get("isDefault", False),
        )
        self.db.add(v)
        await self.db.flush()
        await self.db.refresh(v)
        return _mver_to_dict(v)

    async def update_version(self, version_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        v = result.scalar_one_or_none()
        if not v:
            return None
        field_map = {
            "storagePath": "storage_path", "isDefault": "is_default",
            "fileCount": "file_count",
        }
        for k, val in data.items():
            if val is not None:
                setattr(v, field_map.get(k, k), val)
        v.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(v)
        return _mver_to_dict(v)

    async def set_default_version(self, model_id: str, version_id: str) -> bool:
        # 先取消所有默认
        result = await self.db.execute(
            select(ModelVersion).where(ModelVersion.model_id == model_id)
        )
        for v in result.scalars().all():
            v.is_default = (v.id == version_id)
        await self.db.flush()
        return True

    async def delete_version(self, version_id: str) -> bool:
        result = await self.db.execute(select(ModelVersion).where(ModelVersion.id == version_id))
        v = result.scalar_one_or_none()
        if not v:
            return False
        await self.db.execute(delete(ModelFile).where(ModelFile.version_id == version_id))
        await self.db.delete(v)
        await self.db.flush()
        return True

    # ========== 模型文件 ==========
    async def list_files(self, version_id: str) -> List[Dict]:
        result = await self.db.execute(
            select(ModelFile).where(ModelFile.version_id == version_id)
                .order_by(ModelFile.created_at.desc())
        )
        return [_mfile_to_dict(f) for f in result.scalars().all()]

    async def create_file(self, version_id: str, data: Dict) -> Dict:
        f = ModelFile(
            id=_uuid(),
            version_id=version_id,
            file_name=data.get("fileName"),
            file_path=data.get("filePath"),
            file_size=data.get("fileSize", 0),
            file_type=data.get("fileType", "other"),
            status=data.get("status", "ready"),
        )
        self.db.add(f)
        await self.db.flush()
        await self.db.refresh(f)
        # 更新版本的文件数和大小
        await self._update_version_stats(version_id)
        # 顶层模型 storage_path 为空时，用该版本第一个文件的父目录回写。
        # 训练 executor / 部署推理只读取 Model.storage_path 作为模型路径，
        # 若为空会回退默认 hub id，导致用户上传的模型不被使用；这里在上传
        # 成功后自动补齐，与数据集 create_file 的回写逻辑保持一致。
        file_path = data.get("filePath")
        if file_path and data.get("status", "ready") in ("ready", "success"):
            await self._backfill_model_storage_path(version_id, file_path)
        return _mfile_to_dict(f)

    async def _backfill_model_storage_path(self, version_id: str, file_path: str) -> None:
        """回写顶层 Model.storage_path（仅当其为空时生效）"""
        ver = (await self.db.execute(
            select(ModelVersion).where(ModelVersion.id == version_id)
        )).scalar_one_or_none()
        if not ver:
            return
        m = (await self.db.execute(
            select(Model).where(Model.id == ver.model_id)
        )).scalar_one_or_none()
        if not m or m.storage_path:
            return
        m.storage_path = _dir_of(file_path)
        m.updated_at = _now()
        await self.db.flush()

    async def get_file(self, file_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(ModelFile).where(ModelFile.id == file_id))
        f = result.scalar_one_or_none()
        return _mfile_to_dict(f) if f else None

    async def delete_file(self, file_id: str) -> bool:
        result = await self.db.execute(select(ModelFile).where(ModelFile.id == file_id))
        f = result.scalar_one_or_none()
        if not f:
            return False
        version_id = f.version_id
        await self.db.delete(f)
        await self.db.flush()
        await self._update_version_stats(version_id)
        return True

    async def _update_version_stats(self, version_id: str):
        """更新版本的文件统计信息"""
        result = await self.db.execute(
            select(
                func.count(ModelFile.id),
                func.coalesce(func.sum(ModelFile.file_size), 0),
            ).where(ModelFile.version_id == version_id)
        )
        count, total_size = result.one()
        ver = (await self.db.execute(
            select(ModelVersion).where(ModelVersion.id == version_id)
        )).scalar_one_or_none()
        if ver:
            ver.file_count = count
            ver.size = total_size
            await self.db.flush()

    # ========== 模型对比 ==========
    async def compare_models(self, model_ids: List[str]) -> List[Dict]:
        result = await self.db.execute(
            select(Model).where(Model.id.in_(model_ids))
        )
        models = result.scalars().all()
        out = []
        for m in models:
            d = _model_to_dict(m)
            # 获取版本列表
            ver_result = await self.db.execute(
                select(ModelVersion).where(ModelVersion.model_id == m.id)
                    .order_by(ModelVersion.created_at.desc())
            )
            d["versions"] = [_mver_to_dict(v) for v in ver_result.scalars().all()]
            out.append(d)
        return out

    # ========== 统计 ==========
    async def get_model_stats(self, *, owner_id: Optional[str] = None) -> Dict:
        q = select(func.count(Model.id))
        if owner_id:
            q = q.where(Model.owner_id == owner_id)
        total = (await self.db.execute(q)).scalar() or 0

        public_q = select(func.count(Model.id)).where(Model.is_public == True)
        if owner_id:
            public_q = public_q.where(Model.owner_id == owner_id)
        public_count = (await self.db.execute(public_q)).scalar() or 0

        return {"total": total, "publicCount": public_count}


def _model_to_dict(m: Model) -> Dict:
    return {
        "id": m.id,
        "name": m.name,
        "type": m.type,
        "spec": m.spec,
        "vendor": m.vendor,
        "version": m.version,
        "description": m.description,
        "tags": m.tags,
        "iconUrl": m.icon_url,
        "storagePath": m.storage_path,
        "isPublic": m.is_public,
        "ownerId": m.owner_id,
        "status": m.status,
        "createdAt": m.created_at.isoformat() if m.created_at else None,
        "updatedAt": m.updated_at.isoformat() if m.updated_at else None,
    }


def _mver_to_dict(v: ModelVersion) -> Dict:
    return {
        "id": v.id,
        "modelId": v.model_id,
        "version": v.version,
        "description": v.description,
        "storagePath": v.storage_path,
        "framework": v.framework,
        "size": v.size,
        "fileCount": v.file_count,
        "status": v.status,
        "isDefault": v.is_default,
        "createdAt": v.created_at.isoformat() if v.created_at else None,
        "updatedAt": v.updated_at.isoformat() if v.updated_at else None,
    }


def _mfile_to_dict(f: ModelFile) -> Dict:
    return {
        "id": f.id,
        "versionId": f.version_id,
        "fileName": f.file_name,
        "filePath": f.file_path,
        "fileSize": f.file_size,
        "fileType": f.file_type,
        "status": f.status,
        "createdAt": f.created_at.isoformat() if f.created_at else None,
    }
