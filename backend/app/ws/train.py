"""训练任务实时日志 WebSocket

基于数据库增量轮询推送新日志（不依赖 Redis Pub/Sub，单机/多机均可工作）。
前端连接: ws://host:8000/api/ws/train/{task_id}
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.task_log import TrainTaskLog

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/train/{task_id}")
async def train_log_ws(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    last_seq: int = 0
    try:
        while True:
            async with AsyncSessionLocal() as session:
                query = (
                    select(TrainTaskLog)
                    .where(TrainTaskLog.task_id == task_id, TrainTaskLog.seq > last_seq)
                    .order_by(TrainTaskLog.seq)
                    .limit(200)
                )
                rows = (await session.execute(query)).scalars().all()
            for row in rows:
                await websocket.send_json({
                    "seq": row.seq,
                    "time": row.time.isoformat() if row.time else "",
                    "level": row.level,
                    "message": row.message,
                })
                last_seq = row.seq
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
