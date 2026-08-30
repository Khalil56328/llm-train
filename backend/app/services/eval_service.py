"""模型评测服务"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.dataset import DatasetVersion
from app.models.evaluation import EvaluationTask, EvalItem


def _storage_dir() -> Path:
    """本地存储根目录（与 executor.storage_dir 一致：评测报告所在处）"""
    base = Path(getattr(settings, "LOCAL_STORAGE_DIR", "storage"))
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent.parent / base
    return base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now()


class EvalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_evaluations(
        self,
        *,
        page_index: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        eval_type: Optional[str] = None,
    ) -> Dict:
        q = select(EvaluationTask)
        count_q = select(func.count(EvaluationTask.id))

        if keyword:
            f = EvaluationTask.name.contains(keyword)
            q, count_q = q.where(f), count_q.where(f)
        if status:
            q, count_q = q.where(EvaluationTask.status == status), count_q.where(EvaluationTask.status == status)
        if eval_type:
            q, count_q = q.where(EvaluationTask.eval_type == eval_type), count_q.where(EvaluationTask.eval_type == eval_type)

        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(EvaluationTask.created_at.desc())
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()

        return {
            "list": [_eval_to_dict(e) for e in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def get_evaluation(self, eval_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(EvaluationTask).where(EvaluationTask.id == eval_id))
        e = result.scalar_one_or_none()
        if not e:
            return None
        d = _eval_to_dict(e)
        # dataset_version 入库为版本 ID，此处解析为版本号（如 v1）展示
        if d.get("datasetVersion"):
            ver = await self.db.get(DatasetVersion, d["datasetVersion"])
            if ver is not None:
                d["datasetVersion"] = ver.version
        return d

    async def create_evaluation(self, data: Dict, *, created_by: str) -> Dict:
        e = EvaluationTask(
            id=_uuid(),
            name=data.get("name"),
            description=data.get("description"),
            eval_type=data.get("evalType", "auto"),
            is_baseline=data.get("isBaseline", False),
            dataset_id=data.get("datasetId", ""),
            dataset_name=data.get("datasetName"),
            dataset_version=data.get("datasetVersion"),
            deployment_id=data.get("deploymentId", ""),
            deployment_name=data.get("deploymentName"),
            scenes=data.get("scenes", []),
            metrics=data.get("metrics", []),
            rating_scale=data.get("ratingScale", 5),
            status="pending",
            progress=0,
            created_by=created_by,
        )
        self.db.add(e)
        await self.db.flush()
        await self.db.refresh(e)
        # 人工评测项由任务执行器在生成真实模型回复后创建（见 executor.run_evaluation）
        return _eval_to_dict(e)

    async def update_evaluation(self, eval_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(EvaluationTask).where(EvaluationTask.id == eval_id))
        e = result.scalar_one_or_none()
        if not e:
            return None
        field_map = {
            "isBaseline": "is_baseline", "datasetId": "dataset_id",
            "datasetName": "dataset_name", "datasetVersion": "dataset_version",
            "deploymentId": "deployment_id",
            "deploymentName": "deployment_name", "reportUrl": "report_url",
            "createdBy": "created_by", "errorMessage": "error_message",
            "evalType": "eval_type", "ratingScale": "rating_scale",
        }
        for k, v in data.items():
            if v is not None:
                setattr(e, field_map.get(k, k), v)
        await self.db.flush()
        await self.db.refresh(e)
        return _eval_to_dict(e)

    async def update_eval_status(
        self, eval_id: str, status: str, *,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
        score: Optional[float] = None,
        report_url: Optional[str] = None,
    ) -> Optional[Dict]:
        result = await self.db.execute(select(EvaluationTask).where(EvaluationTask.id == eval_id))
        e = result.scalar_one_or_none()
        if not e:
            return None
        e.status = status
        if progress is not None:
            e.progress = progress
        if error_message is not None:
            e.error_message = error_message
        if score is not None:
            e.score = score
        if report_url is not None:
            e.report_url = report_url
        if status == "completed":
            e.finished_at = _now()
            e.progress = 100
        if status == "running" and e.progress == 0:
            e.progress = 10
        await self.db.flush()
        await self.db.refresh(e)
        return _eval_to_dict(e)

    async def delete_evaluation(self, eval_id: str) -> bool:
        # 先删除关联评测项
        await self.db.execute(delete(EvalItem).where(EvalItem.eval_id == eval_id))
        result = await self.db.execute(select(EvaluationTask).where(EvaluationTask.id == eval_id))
        e = result.scalar_one_or_none()
        if not e:
            return False
        await self.db.delete(e)
        await self.db.flush()
        return True

    async def get_eval_stats(self, *, eval_type: Optional[str] = None) -> Dict:
        q_status = select(EvaluationTask.status, func.count(EvaluationTask.id)).group_by(EvaluationTask.status)
        q_avg = select(func.avg(EvaluationTask.score)).where(EvaluationTask.score.isnot(None))
        if eval_type:
            q_status = q_status.where(EvaluationTask.eval_type == eval_type)
            q_avg = q_avg.where(EvaluationTask.eval_type == eval_type)
        rows = (await self.db.execute(q_status)).all()
        stats = {row[0]: row[1] for row in rows}
        total = sum(stats.values())
        avg_result = await self.db.execute(q_avg)
        avg_score = avg_result.scalar()
        return {
            "pending": stats.get("pending", 0),
            "running": stats.get("running", 0),
            "completed": stats.get("completed", 0),
            "failed": stats.get("failed", 0),
            "total": total,
            "avgScore": round(float(avg_score), 2) if avg_score else None,
        }

    # ---- 人工评测项 ----
    async def list_eval_items(
        self,
        eval_id: str,
        *,
        page_index: int = 1,
        page_size: int = 20,
        is_evaluated: Optional[bool] = None,
    ) -> Dict:
        q = select(EvalItem).where(EvalItem.eval_id == eval_id)
        count_q = select(func.count(EvalItem.id)).where(EvalItem.eval_id == eval_id)
        if is_evaluated is not None:
            q = q.where(EvalItem.is_evaluated == is_evaluated)
            count_q = count_q.where(EvalItem.is_evaluated == is_evaluated)
        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(EvalItem.created_at)
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()
        return {
            "list": [_item_to_dict(i) for i in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def get_eval_item(self, item_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(EvalItem).where(EvalItem.id == item_id))
        i = result.scalar_one_or_none()
        return _item_to_dict(i) if i else None

    async def score_eval_item(self, item_id: str, score: int, *, evaluated_by: str) -> Optional[Dict]:
        result = await self.db.execute(select(EvalItem).where(EvalItem.id == item_id))
        i = result.scalar_one_or_none()
        if not i:
            return None
        i.score = score
        i.is_evaluated = True
        i.evaluated_by = evaluated_by
        i.evaluated_at = _now()
        await self.db.flush()
        await self.db.refresh(i)
        # 更新评测任务进度
        await self._update_manual_progress(i.eval_id)
        return _item_to_dict(i)

    async def _update_manual_progress(self, eval_id: str):
        """更新人工评测进度（模型推理阶段占 0-50%，人工评审占 50-100%）"""
        total_q = select(func.count(EvalItem.id)).where(EvalItem.eval_id == eval_id)
        done_q = select(func.count(EvalItem.id)).where(EvalItem.eval_id == eval_id, EvalItem.is_evaluated == True)
        total = (await self.db.execute(total_q)).scalar() or 1
        done = (await self.db.execute(done_q)).scalar() or 0
        progress = min(50 + int(done / total * 50), 99)
        # 如果全部完成，汇总人工评分并生成评测报告
        result = await self.db.execute(select(EvaluationTask).where(EvaluationTask.id == eval_id))
        e = result.scalar_one_or_none()
        if e:
            e.progress = progress
            if done == total and total > 0 and e.eval_type == "manual":
                await self._finalize_manual_report(e, eval_id, total)
            await self.db.flush()

    async def _finalize_manual_report(self, e: EvaluationTask, eval_id: str, total: int):
        """人工评审全部完成：汇总评审结果，生成评测报告文件并结束任务"""
        rows = (await self.db.execute(
            select(EvalItem).where(EvalItem.eval_id == eval_id).order_by(EvalItem.created_at)
        )).scalars().all()
        scale = e.rating_scale or 5
        scored = [i for i in rows if i.is_evaluated and i.score is not None]
        avg_raw = sum(i.score for i in scored) / len(scored) if scored else 0.0
        percent = round(avg_raw / scale * 100, 1)
        reviewers = sorted({i.evaluated_by for i in scored if i.evaluated_by})
        samples = [
            {
                "prompt": i.prompt,
                "referenceResponse": i.reference_response or "",
                "modelResponse": i.model_response or "",
                "score": i.score,
                "humanScore": round(i.score / scale * 100, 1) if i.score is not None else None,
                "evaluatedBy": i.evaluated_by,
            }
            for i in rows
        ]
        report = {
            "evalId": e.id,
            "name": e.name,
            "evalType": "manual",
            "ratingScale": scale,
            "datasetName": e.dataset_name,
            "deploymentName": e.deployment_name,
            "scenes": e.scenes or [],
            "score": round(avg_raw, 2),
            "overallScore": percent,
            "totalSamples": total,
            "reviewerCount": len(reviewers),
            "reviewers": reviewers,
            "dimensionScores": [
                {
                    "dimension": "overall",
                    "dimensionName": "人工综合评分",
                    "weight": 1.0,
                    "desc": "评审员按评分量级对模型回复的综合评分",
                    "score": percent,
                    "sampleCount": len(scored),
                },
            ],
            "samples": samples,
            "summary": (
                f"人工评测完成：{total} 条样本、{len(reviewers)} 位评审员参与，"
                f"平均得分 {round(avg_raw, 2)}/{scale} 分（百分制 {percent} 分）。"
            ),
            "generatedAt": _now().isoformat(timespec="seconds"),
        }
        reports_dir = _storage_dir() / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{e.id}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        e.score = percent
        e.report_url = f"/static/reports/{e.id}.json"
        e.status = "completed"
        e.progress = 100
        e.finished_at = _now()


def _eval_to_dict(e: EvaluationTask) -> Dict:
    return {
        "id": e.id,
        "name": e.name,
        "description": e.description,
        "evalType": e.eval_type,
        "isBaseline": e.is_baseline,
        "datasetId": e.dataset_id,
        "datasetName": e.dataset_name,
        "datasetVersion": e.dataset_version,
        "deploymentId": e.deployment_id,
        "deploymentName": e.deployment_name,
        "scenes": e.scenes,
        "metrics": e.metrics,
        "ratingScale": e.rating_scale,
        "status": e.status,
        "progress": e.progress or 0,
        "errorMessage": e.error_message,
        "score": e.score,
        "reportUrl": e.report_url,
        "createdBy": e.created_by,
        "createdAt": e.created_at.isoformat() if e.created_at else None,
        "finishedAt": e.finished_at.isoformat() if e.finished_at else None,
    }


def _item_to_dict(i: EvalItem) -> Dict:
    return {
        "id": i.id,
        "evalId": i.eval_id,
        "prompt": i.prompt,
        "referenceResponse": i.reference_response,
        "modelResponse": i.model_response,
        "score": i.score,
        "isEvaluated": i.is_evaluated,
        "evaluatedBy": i.evaluated_by,
        "evaluatedAt": i.evaluated_at.isoformat() if i.evaluated_at else None,
        "createdAt": i.created_at.isoformat() if i.created_at else None,
    }
