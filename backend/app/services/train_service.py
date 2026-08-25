"""训练任务服务"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import TrainTask


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now()


class TrainService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tasks(
        self,
        *,
        page_index: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        task_type: Optional[str] = None,
        task_sub_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict:
        q = select(TrainTask)
        count_q = select(func.count(TrainTask.id))

        if keyword:
            f = TrainTask.name.contains(keyword)
            q, count_q = q.where(f), count_q.where(f)
        if task_type:
            q, count_q = q.where(TrainTask.task_type == task_type), count_q.where(TrainTask.task_type == task_type)
        if task_sub_type:
            q, count_q = (
                q.where(TrainTask.task_sub_type == task_sub_type),
                count_q.where(TrainTask.task_sub_type == task_sub_type),
            )
        if status:
            q, count_q = q.where(TrainTask.status == status), count_q.where(TrainTask.status == status)

        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(TrainTask.created_at.desc())
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()

        return {
            "list": [_task_to_dict(t) for t in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def get_task(self, task_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(TrainTask).where(TrainTask.id == task_id))
        t = result.scalar_one_or_none()
        return _task_to_dict(t) if t else None

    async def create_task(self, data: Dict, *, created_by: str) -> Dict:
        t = TrainTask(
            id=_uuid(),
            name=data.get("name"),
            task_type=data.get("taskType"),
            task_sub_type=data.get("taskSubType"),
            sub_type=data.get("subType"),
            status="pending",
            progress=0,
            base_model_id=data.get("baseModelId"),
            base_model_name=data.get("baseModelName"),
            base_model_version=data.get("baseModelVersion"),
            operator_id=data.get("operatorId"),
            operator_version=data.get("operatorVersion"),
            dataset_id=data.get("datasetId"),
            dataset_name=data.get("datasetName"),
            dataset_version=data.get("datasetVersion"),
            framework=data.get("framework"),
            val_dataset_id=data.get("valDatasetId"),
            val_dataset_version=data.get("valDatasetVersion"),
            sft_model_id=data.get("sftModelId"),
            sft_model_version=data.get("sftModelVersion"),
            teacher_model_id=data.get("teacherModelId"),
            teacher_model_version=data.get("teacherModelVersion"),
            calib_dataset_id=data.get("calibDatasetId"),
            calib_dataset_version=data.get("calibDatasetVersion"),
            hyper_params=data.get("hyperParams", {}),
            env_vars=data.get("envVars", {}),
            resource_config=data.get("resourceConfig", {}),
            description=data.get("description"),
            created_by=created_by,
        )
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return _task_to_dict(t)

    async def update_task(self, task_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(TrainTask).where(TrainTask.id == task_id))
        t = result.scalar_one_or_none()
        if not t:
            return None
        field_map = {
            "taskType": "task_type", "taskSubType": "task_sub_type", "subType": "sub_type",
            "baseModelId": "base_model_id", "baseModelName": "base_model_name",
            "baseModelVersion": "base_model_version",
            "operatorId": "operator_id", "operatorVersion": "operator_version",
            "datasetId": "dataset_id", "datasetName": "dataset_name",
            "datasetVersion": "dataset_version", "framework": "framework",
            "valDatasetId": "val_dataset_id", "valDatasetVersion": "val_dataset_version",
            "sftModelId": "sft_model_id", "sftModelVersion": "sft_model_version",
            "teacherModelId": "teacher_model_id", "teacherModelVersion": "teacher_model_version",
            "calibDatasetId": "calib_dataset_id", "calibDatasetVersion": "calib_dataset_version",
            "hyperParams": "hyper_params", "envVars": "env_vars",
            "resourceConfig": "resource_config", "outputModelId": "output_model_id",
            "outputModelName": "output_model_name", "engineCommand": "engine_command",
            "errorMessage": "error_message", "createdBy": "created_by",
        }
        for k, v in data.items():
            if v is not None:
                setattr(t, field_map.get(k, k), v)
        await self.db.flush()
        await self.db.refresh(t)
        return _task_to_dict(t)

    async def update_task_status(
        self, task_id: str, status: str, *, progress: Optional[int] = None,
        error_message: Optional[str] = None, output_model_id: Optional[str] = None,
        output_model_name: Optional[str] = None,
    ) -> Optional[Dict]:
        result = await self.db.execute(select(TrainTask).where(TrainTask.id == task_id))
        t = result.scalar_one_or_none()
        if not t:
            return None
        t.status = status
        if progress is not None:
            t.progress = progress
        if error_message is not None:
            t.error_message = error_message
        if output_model_id is not None:
            t.output_model_id = output_model_id
        if output_model_name is not None:
            t.output_model_name = output_model_name
        if status == "running" and not t.started_at:
            t.started_at = _now()
        if status in ("succeeded", "failed", "stopped"):
            t.finished_at = _now()
            if status == "succeeded":
                t.progress = 100
        await self.db.flush()
        await self.db.refresh(t)
        return _task_to_dict(t)

    async def delete_task(self, task_id: str) -> bool:
        result = await self.db.execute(select(TrainTask).where(TrainTask.id == task_id))
        t = result.scalar_one_or_none()
        if not t:
            return False
        await self.db.delete(t)
        await self.db.flush()
        return True

    async def get_task_stats(self) -> Dict:
        """任务状态统计"""
        result = await self.db.execute(
            select(TrainTask.status, func.count(TrainTask.id)).group_by(TrainTask.status)
        )
        rows = result.all()
        stats = {row[0]: row[1] for row in rows}
        return {
            "pending": stats.get("pending", 0),
            "running": stats.get("running", 0),
            "succeeded": stats.get("succeeded", 0),
            "failed": stats.get("failed", 0),
            "stopped": stats.get("stopped", 0),
            "total": sum(stats.values()),
        }


def _task_to_dict(t: TrainTask) -> Dict:
    return {
        "id": t.id,
        "name": t.name,
        "taskType": t.task_type,
        "taskSubType": t.task_sub_type,
        "subType": t.sub_type,
        "status": t.status,
        "progress": t.progress or 0,
        "errorMessage": t.error_message,
        "baseModelId": t.base_model_id,
        "baseModelName": t.base_model_name,
        "baseModelVersion": t.base_model_version,
        "operatorId": t.operator_id,
        "operatorVersion": t.operator_version,
        "datasetId": t.dataset_id,
        "datasetName": t.dataset_name,
        "datasetVersion": t.dataset_version,
        "framework": t.framework,
        "valDatasetId": t.val_dataset_id,
        "valDatasetVersion": t.val_dataset_version,
        "sftModelId": t.sft_model_id,
        "sftModelVersion": t.sft_model_version,
        "teacherModelId": t.teacher_model_id,
        "teacherModelVersion": t.teacher_model_version,
        "calibDatasetId": t.calib_dataset_id,
        "calibDatasetVersion": t.calib_dataset_version,
        "hyperParams": t.hyper_params,
        "envVars": t.env_vars,
        "resourceConfig": t.resource_config,
        "outputModelId": t.output_model_id,
        "outputModelName": t.output_model_name,
        "engineCommand": t.engine_command,
        "description": t.description,
        "createdBy": t.created_by,
        "createdAt": t.created_at.isoformat() if t.created_at else None,
        "startedAt": t.started_at.isoformat() if t.started_at else None,
        "finishedAt": t.finished_at.isoformat() if t.finished_at else None,
    }
