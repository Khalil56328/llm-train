"""字典数据服务"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dict_data import DictData


class DictService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dict_by_type(self, dict_type: str) -> List[Dict]:
        """按类型获取字典列表"""
        result = await self.db.execute(
            select(DictData).where(
                DictData.dict_type == dict_type,
                DictData.is_enabled == "1",
            ).order_by(DictData.sort_order)
        )
        rows = result.scalars().all()
        return [_dict_to_item(r) for r in rows]

    async def get_all_dicts(self, dict_types: List[str]) -> Dict[str, List[Dict]]:
        """批量获取多个类型的字典"""
        result: Dict[str, List[Dict]] = {}
        for dt in dict_types:
            result[dt] = await self.get_dict_by_type(dt)
        return result

    async def seed_default_dicts(self) -> None:
        """初始化默认字典数据（如表中无数据则插入）"""
        defaults = {
            "dataset_category": [
                ("all", "全部", 0), ("pretrain", "预训练", 1),
                ("finetune", "微调", 2), ("distill", "蒸馏", 3),
                ("reasoning", "推理", 4), ("evaluation", "评测", 5),
            ],
            "dataset_data_type": [
                ("all", "全部", 0), ("SFT", "SFT", 1), ("DPO", "DPO", 2),
                ("KTO", "KTO", 3), ("GRPO", "GRPO", 4), ("GSPO", "GSPO", 5),
                ("CPT", "CPT", 6), ("general", "通用", 7),
            ],
            "model_type": [
                ("all", "全部", 0), ("dialogue", "对话模型", 1),
                ("vision", "视觉模型", 2), ("image-generation", "图像生成", 3),
                ("embedding", "向量模型", 4), ("rerank", "排序模型", 5),
            ],
            "model_spec": [
                ("all", "全部", 0), ("below-10b", "10B以下", 1),
                ("10b-50b", "10B-50B", 2), ("50b-100b", "50B-100B", 3),
                ("above-100b", "100B以上", 4),
            ],
            "train_type": [
                ("all", "全部", 0), ("fine-tune", "微调", 1),
                ("alignment", "对齐", 2), ("compression", "压缩", 3),
                ("pretrain", "预训练", 4), ("scene", "场景化", 5),
            ],
            "train_sub_type": [
                ("all", "全部", 0), ("lora", "LoRA微调", 1),
                ("dpo", "DPO", 2), ("kto", "KTO", 3),
                ("grpo", "GRPO", 4), ("gspo", "GSPO", 5),
                ("sft", "SFT", 6),
            ],
            "eval_scene": [
                ("code", "代码", 0), ("alignment", "对齐", 1),
                ("agent", "Agent", 2), ("safety", "安全", 3),
                ("reasoning", "推理", 4), ("general", "通用", 5),
            ],
            "operator_category": [
                ("all", "全部", 0), ("pretrain", "预训练", 1),
                ("finetune", "大模型微调", 2), ("distill", "模型蒸馏", 3),
                ("inference", "模型推理", 4), ("data", "数据处理", 5),
                ("other", "其他", 6),
            ],
            "operator_type": [
                ("training", "训练", 0), ("inference", "推理", 1),
                ("data", "数据", 2), ("other", "其他", 3),
            ],
            "resource_type": [
                ("CPU", "CPU", 0), ("GPU", "GPU", 1),
            ],
            "deploy_framework": [
                ("vLLM", "vLLM", 0), ("MindIE", "MindIE", 1),
                ("custom", "自定义", 2),
            ],
        }

        for dict_type, items in defaults.items():
            # 检查是否已有数据
            r = await self.db.execute(
                select(DictData).where(DictData.dict_type == dict_type).limit(1)
            )
            if r.scalar_one_or_none():
                continue
            for code, label, sort in items:
                self.db.add(DictData(
                    dict_type=dict_type,
                    dict_code=code,
                    dict_label=label,
                    dict_value=code,
                    sort_order=sort,
                    is_enabled="1",
                ))
        await self.db.flush()


def _dict_to_item(d: DictData) -> Dict:
    return {
        "code": d.dict_code,
        "label": d.dict_label,
        "value": d.dict_value or d.dict_code,
        "sortOrder": d.sort_order,
    }
