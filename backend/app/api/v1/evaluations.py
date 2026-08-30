"""模型评测 API"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.response import success_response
from app.services.eval_service import EvalService
from app.services.notification_service import NotificationService
from app.api.v1.task_dispatch import dispatch_task
from app.tasks.executor import storage_dir
from app.schemas.evaluation import EvaluationCreate, EvaluationUpdate, EvalItemScore

router = APIRouter()


def _load_report(eval_id: str) -> dict:
    """读取评测报告文件，不存在时返回空结构"""
    report_file = storage_dir() / "reports" / f"{eval_id}.json"
    if report_file.exists():
        try:
            return json.loads(report_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


@router.get("")
async def list_evaluations(
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    keyword: str = Query(None),
    status: str = Query(None),
    eval_type: str = Query(None, alias="evalType"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    result = await svc.list_evaluations(
        page_index=page_index, page_size=page_size,
        keyword=keyword, status=status, eval_type=eval_type,
    )
    return success_response(result)


@router.get("/stats")
async def get_eval_stats(
    eval_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    result = await svc.get_eval_stats(eval_type=eval_type)
    return success_response(result)


@router.get("/{eval_id}")
async def get_evaluation(
    eval_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    result = await svc.get_evaluation(eval_id)
    if not result:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    return success_response(result)


@router.post("")
async def create_evaluation(
    data: EvaluationCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    payload = data.model_dump()
    result = await svc.create_evaluation(payload, created_by=user["username"])

    # 创建通知
    notify_svc = NotificationService(db)
    await notify_svc.create_notification(
        title="评测任务创建",
        content=f"评测任务「{payload.get('name', '')}」已创建成功",
        level="info",
        module="evaluation",
        ref_id=result["id"],
    )

    return success_response(result)


@router.put("/{eval_id}")
async def update_evaluation(
    eval_id: str,
    data: EvaluationUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    result = await svc.update_evaluation(eval_id, data.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    return success_response(result)


@router.delete("/{eval_id}")
async def delete_evaluation(
    eval_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    ok = await svc.delete_evaluation(eval_id)
    if not ok:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    return success_response({"message": "删除成功"})


@router.post("/{eval_id}/start")
async def start_evaluation(
    eval_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """启动评测任务：派发到 Celery（或本地后台）执行"""
    svc = EvalService(db)
    e = await svc.get_evaluation(eval_id)
    if not e:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    if e["status"] == "running":
        raise HTTPException(status_code=400, detail="评测任务正在运行中")

    result = await svc.update_eval_status(eval_id, "running", progress=10)
    dispatch = dispatch_task("eval", eval_id)

    # 创建通知
    notify_svc = NotificationService(db)
    await notify_svc.create_notification(
        title="评测任务开始",
        content=f"评测任务「{e.get('name', eval_id)}」已开始执行（调度方式: {dispatch}）",
        level="info",
        module="evaluation",
        ref_id=eval_id,
    )
    return success_response({**result, "dispatch": dispatch})


@router.get("/{eval_id}/report")
async def get_eval_report(
    eval_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """读取评测报告（由评测执行器生成的真实数据）"""
    svc = EvalService(db)
    e = await svc.get_evaluation(eval_id)
    if not e:
        raise HTTPException(status_code=404, detail="评测任务不存在")

    report = _load_report(eval_id)
    return success_response({
        "taskName": e.get("name"),
        "status": e.get("status"),
        "overallScore": report.get("score", e.get("score")),
        "scenes": e.get("scenes", []),
        "dimensionScores": report.get("dimensionScores", []),
        "summary": report.get("summary", ""),
        "generatedAt": report.get("generatedAt"),
        "details": report.get("samples", []),
        "reportUrl": e.get("reportUrl"),
    })


# ---- 人工评测项 ----

@router.get("/{eval_id}/items")
async def list_eval_items(
    eval_id: str,
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    is_evaluated: bool = Query(None, alias="isEvaluated"),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    result = await svc.list_eval_items(
        eval_id, page_index=page_index, page_size=page_size,
        is_evaluated=is_evaluated,
    )
    return success_response(result)


@router.get("/{eval_id}/items/{item_id}")
async def get_eval_item(
    eval_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    result = await svc.get_eval_item(item_id)
    if not result:
        raise HTTPException(status_code=404, detail="评测项不存在")
    return success_response(result)


@router.post("/{eval_id}/items/{item_id}/score")
async def score_eval_item(
    eval_id: str,
    item_id: str,
    data: EvalItemScore,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = EvalService(db)
    result = await svc.score_eval_item(item_id, data.score, evaluated_by=user["username"])
    if not result:
        raise HTTPException(status_code=404, detail="评测项不存在")
    return success_response(result)
