"""临时脚本：检查新任务日志 seq"""
import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.task_log import TrainTaskLog, TrainTaskMetric

TASK_ID = "6662e381594e4288ae8772c07ef234c5"


async def main():
    async with AsyncSessionLocal() as db:
        logs = (await db.execute(
            select(TrainTaskLog).where(TrainTaskLog.task_id == TASK_ID).order_by(TrainTaskLog.seq)
        )).scalars().all()
        print(f"logs total={len(rows := logs)}")
        for r in logs[:5] + logs[-3:]:
            print(f"  seq={r.seq} {(r.message or '')[:60]}")
        metrics = (await db.execute(
            select(TrainTaskMetric).where(TrainTaskMetric.task_id == TASK_ID).order_by(TrainTaskMetric.seq)
        )).scalars().all()
        print(f"metrics total={len(metrics)}")
        for m in metrics[:5]:
            print(f"  seq={m.seq} step={m.step}")


asyncio.run(main())
