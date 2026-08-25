"""计算资源池服务（运维中心）"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_pool import ResourcePool
from app.schemas.resource_pool import ResourcePoolCreate, ResourcePoolOut, ResourcePoolUpdate


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    """返回北京时间（Asia/Shanghai），以 naive datetime 写入 MySQL DATETIME"""
    return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)


def _to_out(pool: ResourcePool) -> ResourcePoolOut:
    return ResourcePoolOut(
        id=pool.id,
        name=pool.name,
        gpu_type=pool.gpu_type or "A100",
        node_count=pool.node_count or 1,
        total_gpu=pool.total_gpu or 0,
        available_gpu=pool.available_gpu or 0,
        status=pool.status or "active",
        description=pool.description,
        created_at=pool.created_at,
        updated_at=pool.updated_at,
    )


class ResourcePoolService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_pools(
        self,
        *,
        page_index: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict:
        """分页查询资源池"""
        conditions = []
        if keyword:
            conditions.append(ResourcePool.name.like(f"%{keyword}%"))
        if status:
            conditions.append(ResourcePool.status == status)

        total = (
            await self.db.execute(
                select(func.count()).select_from(ResourcePool).where(*conditions)
            )
        ).scalar() or 0

        q = (
            select(ResourcePool)
            .where(*conditions)
            .order_by(ResourcePool.created_at.desc())
            .offset((page_index - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.db.execute(q)).scalars().all()

        return {
            "list": [_to_out(r).model_dump() for r in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def get_pool(self, pool_id: str) -> Optional[ResourcePoolOut]:
        """查询单个资源池"""
        row = (
            await self.db.execute(
                select(ResourcePool).where(ResourcePool.id == pool_id)
            )
        ).scalar_one_or_none()
        return _to_out(row) if row else None

    async def create_pool(self, payload: ResourcePoolCreate) -> ResourcePoolOut:
        """创建资源池"""
        pool = ResourcePool(
            id=_uuid(),
            name=payload.name,
            gpu_type=payload.gpu_type or "A100",
            node_count=payload.node_count or 1,
            total_gpu=payload.total_gpu or 0,
            available_gpu=payload.available_gpu or 0,
            status=payload.status or "active",
            description=payload.description,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(pool)
        await self.db.flush()
        await self.db.refresh(pool)
        return _to_out(pool)

    async def update_pool(self, pool_id: str, payload: ResourcePoolUpdate) -> Optional[ResourcePoolOut]:
        """更新资源池"""
        row = (
            await self.db.execute(
                select(ResourcePool).where(ResourcePool.id == pool_id)
            )
        ).scalar_one_or_none()
        if not row:
            return None
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(row)
        return _to_out(row)

    async def delete_pool(self, pool_id: str) -> bool:
        """删除资源池"""
        row = (
            await self.db.execute(
                select(ResourcePool).where(ResourcePool.id == pool_id)
            )
        ).scalar_one_or_none()
        if not row:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True

    async def seed_defaults(self) -> int:
        """初始化默认资源池（仅当表为空时写入）"""
        count = (
            await self.db.execute(select(func.count()).select_from(ResourcePool))
        ).scalar() or 0
        if count > 0:
            return 0
        defaults: List[Dict] = [
            {
                "name": "GPU-A100 训练池",
                "gpu_type": "A100 80G",
                "node_count": 4,
                "total_gpu": 8,
                "available_gpu": 8,
                "status": "active",
                "description": "A100 80G 高性能训练资源池",
            },
            {
                "name": "GPU-H800 训练池",
                "gpu_type": "H800 80G",
                "node_count": 2,
                "total_gpu": 4,
                "available_gpu": 4,
                "status": "active",
                "description": "H800 80G 大模型训练资源池",
            },
            {
                "name": "GPU-V100 训练池",
                "gpu_type": "V100 32G",
                "node_count": 3,
                "total_gpu": 6,
                "available_gpu": 6,
                "status": "active",
                "description": "V100 32G 通用训练资源池",
            },
            {
                "name": "GPU-A10 推理池",
                "gpu_type": "A10 24G",
                "node_count": 5,
                "total_gpu": 10,
                "available_gpu": 10,
                "status": "active",
                "description": "A10 24G 模型推理资源池",
            },
        ]
        now = _now()
        for item in defaults:
            self.db.add(
                ResourcePool(
                    id=_uuid(),
                    created_at=now,
                    updated_at=now,
                    **item,
                )
            )
        await self.db.flush()
        return len(defaults)
