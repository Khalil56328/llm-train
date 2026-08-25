"""任务派发工具：优先 Celery，broker 不可用时本地后台执行

本地无 Redis / 未启动 worker 时，任务以 asyncio 后台任务方式执行，
保证开发环境（Windows 本机）也能验证完整链路。
"""
from __future__ import annotations

import asyncio


def dispatch_task(kind: str, ref_id: str) -> str:
    """派发任务到执行器

    kind: train / inference / eval
    ref_id: 训练任务ID / 部署ID / 评测任务ID
    返回派发方式: "celery" / "local"

    仅当 Celery worker 存活时才投递到队列，否则本地后台执行，
    避免任务投递到 Redis 后无人消费导致一直 running。
    """
    from app.tasks.executor import run_evaluation, run_inference, run_training

    try:
        from app.tasks.worker import (
            celery_app,
            execute_training_task,
            run_evaluation_task,
            start_inference_service,
        )
        # 检查 worker 是否存活（1s 超时，无 worker 返回空列表）
        workers = celery_app.control.ping(timeout=1) or []
        if workers:
            if kind == "train":
                execute_training_task.apply_async(args=[ref_id])
            elif kind == "inference":
                start_inference_service.apply_async(args=[ref_id])
            else:
                run_evaluation_task.apply_async(args=[ref_id])
            return "celery"
    except Exception:
        pass

    # 本地后台执行
    funcs = {"train": run_training, "inference": run_inference, "eval": run_evaluation}
    loop = asyncio.get_running_loop()
    loop.create_task(funcs[kind](ref_id))
    return "local"
