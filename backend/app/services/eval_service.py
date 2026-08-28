"""模型评测服务"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import EvaluationTask, EvalItem


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
        return _eval_to_dict(e) if e else None

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
        # 如果是人工评测，创建评测项
        if e.eval_type == "manual":
            await self._create_manual_items(e.id, data)
        return _eval_to_dict(e)

    async def _create_manual_items(self, eval_id: str, data: Dict):
        """创建人工评测项（模拟数据）"""
        prompts = data.get("evalPrompts", [])
        if not prompts:
            # 生成模拟评测项
            for i in range(5):
                item = EvalItem(
                    id=_uuid(),
                    eval_id=eval_id,
                    prompt=f"示例问题 {i+1}：请解释什么是大语言模型？",
                    reference_response=f"参考回答 {i+1}：大语言模型是一种基于深度学习的自然语言处理模型...",
                    model_response=f"模型回答 {i+1}：大语言模型是经过大规模文本数据训练的AI模型...",
                    score=None,
                    is_evaluated=False,
                )
                self.db.add(item)
        else:
            for p in prompts:
                item = EvalItem(
                    id=_uuid(),
                    eval_id=eval_id,
                    prompt=p.get("prompt", ""),
                    reference_response=p.get("referenceResponse", ""),
                    model_response=p.get("modelResponse", ""),
                    score=None,
                    is_evaluated=False,
                )
                self.db.add(item)
        await self.db.flush()

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
        """更新人工评测进度"""
        total_q = select(func.count(EvalItem.id)).where(EvalItem.eval_id == eval_id)
        done_q = select(func.count(EvalItem.id)).where(EvalItem.eval_id == eval_id, EvalItem.is_evaluated == True)
        total = (await self.db.execute(total_q)).scalar() or 1
        done = (await self.db.execute(done_q)).scalar() or 0
        progress = int(done / total * 100)
        # 如果全部完成，计算平均分并更新状态
        result = await self.db.execute(select(EvaluationTask).where(EvaluationTask.id == eval_id))
        e = result.scalar_one_or_none()
        if e:
            e.progress = progress
            if done == total and total > 0:
                avg_result = await self.db.execute(
                    select(func.avg(EvalItem.score)).where(EvalItem.eval_id == eval_id, EvalItem.score.isnot(None))
                )
                avg_score = avg_result.scalar()
                e.score = round(float(avg_score), 2) if avg_score else None
                e.status = "completed"
                e.finished_at = _now()
            await self.db.flush()


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
