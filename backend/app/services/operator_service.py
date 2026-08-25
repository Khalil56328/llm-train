"""算子中心 - 数据库仓储"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, delete, update, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.operator import Operator, OperatorVersion
from app.models.user import User
from app.schemas.operator import (
    ImageOut,
    OperatorCreate,
    OperatorOut,
    OperatorUpdate,
    OperatorVersionCreate,
    OperatorVersionOut,
    OperatorVersionUpdate,
    OperatorWithVersionsOut,
)


def _now() -> datetime:
    """返回北京时间（Asia/Shanghai），以 naive datetime 写入 MySQL DATETIME"""
    return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)


def _uuid() -> str:
    return uuid.uuid4().hex


class OperatorService:
    """算子数据库服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 算子 ==========
    async def list_operators(
        self,
        *,
        page_index: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        is_public: Optional[bool] = None,
    ) -> Dict:
        q = select(Operator)
        count_q = select(func.count(Operator.id))

        if keyword:
            filter_expr = Operator.name.contains(keyword)
            q = q.where(filter_expr)
            count_q = count_q.where(filter_expr)
        if category and category != "全部":
            q = q.where(Operator.category == category)
            count_q = count_q.where(Operator.category == category)
        if is_public is not None:
            if is_public:
                # 广场可见性：只要算子存在至少一个公开版本即视为公开，
                # 与算子管理中的版本"公开/私有"开关实时联动
                pub_exists = exists().where(
                    OperatorVersion.operator_id == Operator.id,
                    OperatorVersion.is_public.is_(True),
                )
            else:
                pub_exists = Operator.is_public.is_(False)
            q = q.where(pub_exists)
            count_q = count_q.where(pub_exists)

        total_result = await self.db.execute(count_q)
        total = total_result.scalar() or 0

        q = q.order_by(Operator.created_at.desc()) \
             .offset((page_index - 1) * page_size) \
             .limit(page_size)
        result = await self.db.execute(q)
        rows = result.scalars().all()

        owner_map = await self._resolve_owner_names(
            [op.owner_id for op in rows if op.owner_id]
        )
        items = [
            _operator_to_out(op, owner_name=owner_map.get(op.owner_id or ""))
            for op in rows
        ]
        return {
            "list": [i.model_dump() for i in items],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def get_operator(self, operator_id: str) -> Optional[OperatorWithVersionsOut]:
        result = await self.db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        op = result.scalar_one_or_none()
        if not op:
            return None

        versions_result = await self.db.execute(
            select(OperatorVersion).where(OperatorVersion.operator_id == operator_id)
                .order_by(OperatorVersion.created_at.desc())
        )
        versions = versions_result.scalars().all()

        owner_name = None
        if op.owner_id:
            owner_map = await self._resolve_owner_names([op.owner_id])
            owner_name = owner_map.get(op.owner_id)
        return OperatorWithVersionsOut(
            **_operator_to_out(op, owner_name=owner_name).model_dump(),
            versions=[_version_to_out(v) for v in versions],
        )

    async def create_operator(
        self,
        payload: OperatorCreate,
        *,
        owner: str,
        owner_name: Optional[str] = None,
    ) -> OperatorOut:
        op = Operator(
            id=_uuid(),
            name=payload.name,
            category=payload.category,
            type=payload.type,
            training_framework=payload.training_framework,
            training_method=payload.training_method,
            description=payload.description,
            is_public=payload.is_public,
            owner_id=owner,
            version_count=0,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(op)
        await self.db.flush()
        await self.db.refresh(op)
        return _operator_to_out(op, owner_name=owner_name)

    async def update_operator(self, operator_id: str, payload: OperatorUpdate) -> Optional[OperatorOut]:
        result = await self.db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        op = result.scalar_one_or_none()
        if not op:
            return None
        update_data = payload.model_dump(exclude_none=True)
        if update_data:
            for k, v in update_data.items():
                setattr(op, k, v)
            op.updated_at = _now()
            await self.db.flush()
            await self.db.refresh(op)
        return _operator_to_out(op)

    async def delete_operator(self, operator_id: str) -> bool:
        result = await self.db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        op = result.scalar_one_or_none()
        if not op:
            return False
        # 级联删除版本
        await self.db.execute(
            delete(OperatorVersion).where(OperatorVersion.operator_id == operator_id)
        )
        await self.db.delete(op)
        await self.db.flush()
        return True

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

    # ========== 算子版本 ==========
    async def list_versions(self, operator_id: str) -> List[OperatorVersionOut]:
        result = await self.db.execute(
            select(OperatorVersion).where(OperatorVersion.operator_id == operator_id)
                .order_by(OperatorVersion.created_at.desc())
        )
        rows = result.scalars().all()
        return [_version_to_out(v) for v in rows]

    async def get_version(self, version_id: str) -> Optional[OperatorVersionOut]:
        result = await self.db.execute(
            select(OperatorVersion).where(OperatorVersion.id == version_id)
        )
        v = result.scalar_one_or_none()
        if not v:
            return None
        return _version_to_out(v)

    async def create_version(
        self, operator_id: str, payload: OperatorVersionCreate, *, creator: str
    ) -> Optional[OperatorVersionOut]:
        # 检查算子是否存在
        op_result = await self.db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        op = op_result.scalar_one_or_none()
        if not op:
            return None

        ver = OperatorVersion(
            id=_uuid(),
            operator_id=operator_id,
            name=payload.name,
            description=payload.description,
            resource_type=payload.resource_type,
            base_image=payload.base_image,
            work_dir=payload.work_dir,
            start_cmd=payload.start_cmd,
            mount_dir=payload.mount_dir,
            start_params=payload.start_params,
            is_public=payload.is_public,
            creator=creator,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(ver)

        # 更新算子的版本计数（先 flush 确保新版本已落库，再统计实际数量，
        # 避免 autoflush 把待插入的新版本计入后再 +1 导致重复累加）
        await self.db.flush()
        count_result = await self.db.execute(
            select(func.count(OperatorVersion.id)).where(
                OperatorVersion.operator_id == operator_id
            )
        )
        new_count = count_result.scalar() or 0
        await self.db.execute(
            update(Operator).where(Operator.id == operator_id).values(
                version_count=new_count, updated_at=_now()
            )
        )

        await self.db.flush()
        await self.db.refresh(ver)
        return _version_to_out(ver)

    async def update_version(
        self, version_id: str, payload: OperatorVersionUpdate
    ) -> Optional[OperatorVersionOut]:
        result = await self.db.execute(
            select(OperatorVersion).where(OperatorVersion.id == version_id)
        )
        ver = result.scalar_one_or_none()
        if not ver:
            return None
        update_data = payload.model_dump(exclude_none=True)
        if update_data:
            for k, v in update_data.items():
                setattr(ver, k, v)
            ver.updated_at = _now()
            await self.db.flush()
            await self.db.refresh(ver)
        return _version_to_out(ver)

    async def delete_version(self, version_id: str) -> bool:
        result = await self.db.execute(
            select(OperatorVersion).where(OperatorVersion.id == version_id)
        )
        ver = result.scalar_one_or_none()
        if not ver:
            return False
        operator_id = ver.operator_id
        await self.db.delete(ver)

        # 更新算子的版本计数
        count_result = await self.db.execute(
            select(func.count(OperatorVersion.id)).where(
                OperatorVersion.operator_id == operator_id
            )
        )
        new_count = count_result.scalar() or 0
        await self.db.execute(
            update(Operator).where(Operator.id == operator_id).values(
                version_count=new_count, updated_at=_now()
            )
        )
        await self.db.flush()
        return True

    # ========== 镜像（复用运维中心镜像资源） ==========
    async def list_images(
        self,
        *,
        page_index: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> Dict:
        from app.services.image_service import ImageService

        svc = ImageService(self.db)
        return await svc.list_images(
            page_index=page_index,
            page_size=page_size,
            keyword=keyword,
            resource_type=resource_type,
        )


# ========== 辅助转换函数 ==========
def _operator_to_out(op: Operator, owner_name: Optional[str] = None) -> OperatorOut:
    return OperatorOut(
        id=op.id,
        name=op.name,
        category=op.category,
        type=op.type,
        training_framework=op.training_framework,
        training_method=op.training_method,
        description=op.description,
        version_count=op.version_count or 0,
        owner=op.owner_id or "",
        owner_name=owner_name,
        is_public=op.is_public or False,
        created_at=op.created_at,
        updated_at=op.updated_at,
    )


def _version_to_out(v: OperatorVersion) -> OperatorVersionOut:
    return OperatorVersionOut(
        id=v.id,
        operator_id=v.operator_id,
        name=v.name,
        description=v.description,
        resource_type=v.resource_type or "CPU",
        base_image=v.base_image,
        image_address=v.base_image,
        image_name=None,
        work_dir=v.work_dir,
        start_cmd=v.start_cmd,
        mount_dir=v.mount_dir,
        start_params=v.start_params,
        is_public=v.is_public or False,
        creator=v.creator,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )
