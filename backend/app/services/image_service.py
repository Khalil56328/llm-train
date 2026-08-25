"""镜像资源服务（运维中心）"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image import DockerImage
from app.schemas.image import ImageCreate, ImageOut, ImageUpdate


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    """返回北京时间（Asia/Shanghai），以 naive datetime 写入 MySQL DATETIME"""
    return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)


def _to_out(img: DockerImage) -> ImageOut:
    return ImageOut(
        id=img.id,
        name=img.name,
        address=img.address,
        resource_type=img.resource_type or "CPU",
        description=img.description,
        created_at=img.created_at,
        updated_at=img.updated_at,
    )


class ImageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_images(
        self,
        *,
        page_index: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> Dict:
        """分页查询镜像"""
        conditions = []
        if keyword:
            conditions.append(DockerImage.name.like(f"%{keyword}%"))
        if resource_type:
            conditions.append(DockerImage.resource_type == resource_type)

        total = (
            await self.db.execute(
                select(func.count()).select_from(DockerImage).where(*conditions)
            )
        ).scalar() or 0

        q = (
            select(DockerImage)
            .where(*conditions)
            .order_by(DockerImage.created_at.desc())
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

    async def get_image(self, image_id: str) -> Optional[ImageOut]:
        """查询单个镜像"""
        row = (
            await self.db.execute(
                select(DockerImage).where(DockerImage.id == image_id)
            )
        ).scalar_one_or_none()
        return _to_out(row) if row else None

    async def create_image(self, payload: ImageCreate) -> ImageOut:
        """创建镜像"""
        img = DockerImage(
            id=_uuid(),
            name=payload.name,
            address=payload.address,
            resource_type=payload.resource_type or "CPU",
            description=payload.description,
            created_at=_now(),
            updated_at=_now(),
        )
        self.db.add(img)
        await self.db.flush()
        await self.db.refresh(img)
        return _to_out(img)

    async def update_image(self, image_id: str, payload: ImageUpdate) -> Optional[ImageOut]:
        """更新镜像"""
        row = (
            await self.db.execute(
                select(DockerImage).where(DockerImage.id == image_id)
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

    async def delete_image(self, image_id: str) -> bool:
        """删除镜像"""
        row = (
            await self.db.execute(
                select(DockerImage).where(DockerImage.id == image_id)
            )
        ).scalar_one_or_none()
        if not row:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True

    async def seed_defaults(self) -> int:
        """初始化默认镜像（仅当表为空时写入）"""
        count = (
            await self.db.execute(select(func.count()).select_from(DockerImage))
        ).scalar() or 0
        if count > 0:
            return 0
        defaults: List[Dict] = [
            {
                "name": "ModelScope 宿主机环境镜像",
                "address": "ubuntu22.04-cuda12.8.1-py312-torch2.10.0-1.39.0",
                "resource_type": "GPU",
                "description": "魔搭 Notebook 宿主机实际运行环境（Ubuntu 22.04 / CUDA 12.8.1 / Python 3.12 / torch 2.10.0）；TRAIN_CONTAINER_RUNTIME=local 时训练/推理直接在此环境执行",
            },
            {
                "name": "PyTorch 2.10.0-CUDA12.8",
                "address": "pytorch/pytorch:2.10.0-cuda12.8-cudnn9-runtime",
                "resource_type": "GPU",
                "description": "PyTorch 2.10.0 + CUDA 12.8，与 ModelScope Notebook 镜像（torch 2.10.0 / CUDA 12.8.1）一致，适用于容器化训练/微调",
            },
            {
                "name": "PyTorch 2.10.0-CPU",
                "address": "pytorch/pytorch:2.10.0-cpu",
                "resource_type": "CPU",
                "description": "PyTorch 2.10.0 CPU 版，适用于 CPU 推理与轻量任务",
            },
            {
                "name": "vLLM OpenAI-最新",
                "address": "vllm/vllm-openai:latest",
                "resource_type": "GPU",
                "description": "vLLM OpenAI 兼容推理服务镜像，适用于大模型高效推理",
            },
            {
                "name": "Ubuntu 22.04-Base",
                "address": "ubuntu:22.04",
                "resource_type": "CPU",
                "description": "Ubuntu 22.04 基础镜像",
            },
        ]
        now = _now()
        for item in defaults:
            self.db.add(
                DockerImage(
                    id=_uuid(),
                    created_at=now,
                    updated_at=now,
                    **item,
                )
            )
        await self.db.flush()
        return len(defaults)
