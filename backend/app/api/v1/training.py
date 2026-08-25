"""训练任务 API"""
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.response import success_response
from app.engine.swift.adapter import SwiftEngineAdapter
from app.services.train_service import TrainService
from app.services.notification_service import NotificationService
from app.services.task_log_service import TaskLogService
from app.tasks.control import set_control
from app.tasks.executor import resolve_operator_version
from app.api.v1.task_dispatch import dispatch_task
from app.schemas.train import TrainTaskCreate, TrainTaskUpdate

router = APIRouter()

# 允许提交的任务状态
SUBMITTABLE_STATUS = ("pending", "failed", "stopped")


async def _validate_operator_params(db: AsyncSession, task: Dict) -> Optional[str]:
    """提交前按算子参数契约校验（回填默认值 + 必填/取值校验），返回错误信息或 None"""
    operator_id = task.get("operatorId")
    if not operator_id:
        return None
    ver = await resolve_operator_version(db, operator_id, task.get("operatorVersion"))
    if not ver:
        return f"算子版本未找到（operator_id={operator_id}, version={task.get('operatorVersion') or '-'}）"
    _, err = SwiftEngineAdapter.resolve_hyper_params(
        dict(task.get("hyperParams") or {}), ver.start_params
    )
    return err


@router.get("")
async def list_tasks(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    # 兼容前端驼峰 taskType 与外部蛇形 task_type 两种传参
    task_type: str = Query(None, alias="taskType"),
    task_type_snake: str = Query(None, alias="task_type"),
    # 任务子类型/模态筛选（预训练页：文本生成/图像生成/图像理解）
    task_sub_type: str = Query(None, alias="taskSubType"),
    task_sub_type_snake: str = Query(None, alias="task_sub_type"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = TrainService(db)
    result = await svc.list_tasks(
        page_index=page_index, page_size=page_size,
        keyword=keyword, task_type=task_type or task_type_snake, status=status,
        task_sub_type=task_sub_type or task_sub_type_snake,
    )
    return success_response(result)


@router.get("/stats")
async def get_task_stats(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = TrainService(db)
    result = await svc.get_task_stats()
    return success_response(result)


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = TrainService(db)
    result = await svc.get_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    return success_response(result)


@router.post("")
async def create_task(
    data: TrainTaskCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = TrainService(db)
    payload = data.model_dump(by_alias=True)
    result = await svc.create_task(payload, created_by=user["username"])

    # 创建通知
    notify_svc = NotificationService(db)
    await notify_svc.create_notification(
        title="训练任务创建",
        content=f"训练任务「{payload.get('name', '')}」已创建成功",
        level="info",
        module="training",
        ref_id=result["id"],
    )

    return success_response(result)


@router.put("/{task_id}")
async def update_task(
    task_id: str,
    data: TrainTaskUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = TrainService(db)
    result = await svc.update_task(task_id, data.model_dump(by_alias=True, exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    return success_response(result)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = TrainService(db)
    ok = await svc.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    return success_response({"message": "删除成功"})


@router.post("/{task_id}/submit")
async def submit_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """提交训练任务：更新状态并派发到 Celery（或本地后台）执行"""
    svc = TrainService(db)
    task = await svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    if task["status"] not in SUBMITTABLE_STATUS:
        raise HTTPException(status_code=400, detail=f"任务当前状态为 {task['status']}，无法提交")

    # 算子参数契约校验（默认值回填 + 必填/取值校验），失败则不允许提交
    op_err = await _validate_operator_params(db, task)
    if op_err:
        raise HTTPException(status_code=400, detail=f"算子参数校验失败：{op_err}")

    result = await svc.update_task_status(task_id, "running", progress=5)

    # 派发执行（Celery 优先，本地 fallback）
    dispatch = dispatch_task("train", task_id)

    # 创建通知
    notify_svc = NotificationService(db)
    await notify_svc.create_notification(
        title="训练任务开始",
        content=f"训练任务「{task.get('name', task_id)}」已开始执行（调度方式: {dispatch}）",
        level="info",
        module="training",
        ref_id=task_id,
    )

    return success_response({**result, "dispatch": dispatch})


@router.post("/{task_id}/pause")
async def pause_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """暂停运行中的训练任务"""
    svc = TrainService(db)
    task = await svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    if task["status"] != "running":
        raise HTTPException(status_code=400, detail="仅运行中的任务可暂停")
    set_control(task_id, "pause")
    return success_response({"id": task_id, "status": "paused"}, message="暂停指令已下发")


@router.post("/{task_id}/resume")
async def resume_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """恢复已暂停的训练任务"""
    svc = TrainService(db)
    task = await svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    if task["status"] != "paused":
        raise HTTPException(status_code=400, detail="仅已暂停的任务可恢复")
    set_control(task_id, "resume")
    return success_response({"id": task_id, "status": "running"}, message="恢复指令已下发")


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """取消训练任务"""
    svc = TrainService(db)
    task = await svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    if task["status"] not in ("running", "paused", "pending"):
        raise HTTPException(status_code=400, detail=f"任务当前状态为 {task['status']}，无法取消")
    set_control(task_id, "cancel")
    result = await svc.update_task_status(task_id, "stopped")
    return success_response(result, message="取消指令已下发")


@router.post("/{task_id}/stop")
async def stop_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """停止训练任务（等价于取消）"""
    return await cancel_task(task_id, db, _user)


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """重试失败/停止的训练任务"""
    svc = TrainService(db)
    task = await svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    if task["status"] not in ("failed", "stopped"):
        raise HTTPException(status_code=400, detail=f"任务当前状态为 {task['status']}，无法重试")

    # 算子参数契约校验（与提交一致）
    op_err = await _validate_operator_params(db, task)
    if op_err:
        raise HTTPException(status_code=400, detail=f"算子参数校验失败：{op_err}")

    result = await svc.update_task_status(task_id, "running", progress=5)
    dispatch = dispatch_task("train", task_id)

    notify_svc = NotificationService(db)
    await notify_svc.create_notification(
        title="训练任务重试",
        content=f"训练任务「{task.get('name', task_id)}」已重新执行（调度方式: {dispatch}）",
        level="info",
        module="training",
        ref_id=task_id,
    )
    return success_response({**result, "dispatch": dispatch})


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    tail: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = TrainService(db)
    task = await svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    log_svc = TaskLogService(db)
    rows = await log_svc.list_logs(task_id, tail=tail)
    return success_response(rows)


@router.get("/{task_id}/metrics")
async def get_task_metrics(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = TrainService(db)
    task = await svc.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    log_svc = TaskLogService(db)
    rows = await log_svc.list_metrics(task_id)
    return success_response(rows)
