"""Celery Worker - 训练/推理/评测任务执行

执行逻辑统一委托给 app.tasks.executor，保证 Celery 与 API 本地调度行为一致。

重要（事件循环与 async 引擎连接池）：
executor 与 SQLAlchemy async 引擎（AsyncSessionLocal）共用全局单例，
asyncmy 连接在创建时绑定到当时的 asyncio 事件循环，且该绑定无法跨循环复用。
因此本 worker 进程必须复用「单一常驻事件循环」执行所有协程任务，
否则若每个任务都用 asyncio.run() 各自新建循环，第二个任务会从连接池
checkout 到绑定已关闭旧循环的连接，抛出
"got Future <Future pending> attached to a different loop"。
"""
import asyncio
import threading
import time
from typing import Callable

from celery import Celery

from app.core.config import settings
from app.tasks.executor import run_evaluation, run_inference, run_training

celery_app = Celery(
    "llm_train",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
)


# ---------------------------------------------------------------------------
# 单一常驻事件循环：避免 asyncio.run() 每次新建循环导致 async 引擎连接池跨循环复用
# ---------------------------------------------------------------------------

_loop: "asyncio.AbstractEventLoop | None" = None


def _run_event_loop() -> None:
    """在守护线程中启动并运行常驻事件循环（进程内唯一）。"""
    global _loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop = loop
    loop.run_forever()


def _ensure_loop() -> "asyncio.AbstractEventLoop":
    """惰性启动常驻事件循环（幂等），返回它。"""
    global _loop
    if _loop is not None and not _loop.is_closed():
        return _loop
    threading.Thread(target=_run_event_loop, name="worker-asyncio-loop", daemon=True).start()
    # 等待循环就绪
    while _loop is None or _loop.is_closed():
        time.sleep(0.01)
    return _loop


def _submit(coro_factory: Callable[[], "asyncio.coroutines.Coroutine"]) -> str:
    """将协程任务提交到进程内唯一的常驻事件循环，同步等待并返回执行结果字符串。

    因所有任务共用同一个事件循环，async 引擎（AsyncSessionLocal）连接池
    的连接始终绑定到该循环，不会出现跨循环复用导致的
    "got Future attached to a different loop" 错误。
    """
    loop = _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro_factory(), loop).result()


@celery_app.task(bind=True, name="train.execute_task", max_retries=0)
def execute_training_task(self, task_id: str) -> str:
    """执行训练任务"""
    return _submit(lambda: run_training(task_id))


@celery_app.task(bind=True, name="inference.start_service", max_retries=0)
def start_inference_service(self, deployment_id: str) -> str:
    """启动推理服务"""
    return _submit(lambda: run_inference(deployment_id))


@celery_app.task(bind=True, name="eval.run_evaluation", max_retries=0)
def run_evaluation_task(self, eval_id: str) -> str:
    """执行评测任务"""
    return _submit(lambda: run_evaluation(eval_id))
