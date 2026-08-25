"""训练任务日志 / 指标查询服务"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_log import TrainTaskLog, TrainTaskMetric


class TaskLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_logs(self, task_id: str, *, tail: int = 200) -> List[Dict]:
        """按 seq 倒序读取最近 tail 条日志，返回正序列表"""
        rows = (await self.db.execute(
            select(TrainTaskLog)
            .where(TrainTaskLog.task_id == task_id)
            .order_by(TrainTaskLog.seq.desc())
            .limit(tail)
        )).scalars().all()
        rows = list(reversed(rows))
        return [
            {
                "time": r.time.isoformat() if r.time else "",
                "level": r.level or "INFO",
                "message": r.message or "",
            }
            for r in rows
        ]

    async def list_metrics(self, task_id: str, *, limit: int = 500) -> List[Dict]:
        rows = (await self.db.execute(
            select(TrainTaskMetric)
            .where(TrainTaskMetric.task_id == task_id)
            .order_by(TrainTaskMetric.seq.desc())
            .limit(limit)
        )).scalars().all()
        rows = list(reversed(rows))
        return [
            {
                "step": r.step or 0,
                "loss": r.loss,
                "lr": r.lr,
            }
            for r in rows
        ]
