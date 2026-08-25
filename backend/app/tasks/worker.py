"""Celery Worker - 训练/推理/评测任务执行

执行逻辑统一委托给 app.tasks.executor，保证 Celery 与 API 本地调度行为一致。
"""
import asyncio

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


@celery_app.task(bind=True, name="train.execute_task", max_retries=0)
def execute_training_task(self, task_id: str) -> str:
    """执行训练任务"""
    return asyncio.run(run_training(task_id))


@celery_app.task(bind=True, name="inference.start_service", max_retries=0)
def start_inference_service(self, deployment_id: str) -> str:
    """启动推理服务"""
    return asyncio.run(run_inference(deployment_id))


@celery_app.task(bind=True, name="eval.run_evaluation", max_retries=0)
def run_evaluation_task(self, eval_id: str) -> str:
    """执行评测任务"""
    return asyncio.run(run_evaluation(eval_id))
