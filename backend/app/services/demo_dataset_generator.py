"""演示数据集生成器（后端内置，启动时自愈）

不依赖部署脚本（deploy/common/seed_demo_data.py）是否执行成功：
后端每次启动时检查 workspace/datasets/ 下三个演示数据集
（SFT / 偏好 DPO / 预训练 CPT）的文件是否完整，缺失则本地生成，
保证"数据库记录"与"磁盘文件"始终一致。

数据内容与 deploy/common/seed_demo_data.py 保持一致：
- SFT：self-cognition 风格固定问答对（messages 格式）
- 偏好：由 SFT 轮次派生 chosen / rejected（DPO 训练格式）
- 预训练：由 SFT 轮次拼接纯文本（CPT 训练格式）
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import List, Optional

# 三个演示数据集目录名（与部署脚本保持一致）
SFT_DIR_NAME = "sft_self_cognition"
PREF_DIR_NAME = "preference_demo"
PT_DIR_NAME = "pretrain_demo"
DEMO_DATASET_DIRS = (SFT_DIR_NAME, PREF_DIR_NAME, PT_DIR_NAME)

SFT_META = {
    "name": "self-cognition 演示SFT数据集",
    "type": "training",
    "data_type": "SFT",
    "category": "文本生成",
    "description": "平台内置演示：自我认知小样本数据，用于 SFT 微调向导开箱体验",
    "sample_count": 20,
}
PREF_META = {
    "name": "preference-demo 偏好对齐演示数据集",
    "type": "training",
    "data_type": "DPO",
    "category": "文本生成",
    "description": "平台内置演示：由演示 SFT 数据派生的偏好对（chosen/rejected），用于 DPO/KTO/ORPO 对齐向导开箱体验",
    "sample_count": 20,
}
PT_META = {
    "name": "pretrain-demo 预训练演示数据集",
    "type": "training",
    "data_type": "CPT",
    "category": "文本生成",
    "description": "平台内置演示：由演示 SFT 数据派生的预训练纯文本，用于续训/预训练向导开箱体验",
    "sample_count": 20,
}

SFT_SELF_COGNITION_ROWS: List[dict] = [
    {"conversations": [
        {"from": "user", "value": "你是谁？"},
        {"from": "assistant", "value": "我是由本平台训练的大语言模型，可以协助你完成问答、写作、代码等任务。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "你能做什么？"},
        {"from": "assistant", "value": "我可以进行多轮对话、文案生成、代码解释、知识问答等，具体能力取决于训练数据与微调方式。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "你的训练流程是怎样的？"},
        {"from": "assistant", "value": "我经历了预训练、指令微调（SFT）与人类偏好对齐（DPO）三个阶段，全部在本平台上完成编排。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "什么是 SFT？"},
        {"from": "assistant", "value": "SFT（Supervised Fine-Tuning）即监督微调，使用人工标注的指令-回答对调整模型行为，是当前最常见的微调方式。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "什么是 DPO？"},
        {"from": "assistant", "value": "DPO（Direct Preference Optimization）直接偏好优化，无需显式奖励模型即可依据偏好对对齐模型输出，训练更稳定。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "什么是 LoRA？"},
        {"from": "assistant", "value": "LoRA 通过低秩适配矩阵注入可训练参数，仅训练极少量参数即可获得接近全参微调的效果，显存占用小。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "如何评估一个大模型的好坏？"},
        {"from": "assistant", "value": "通常从通用能力评测（C-Eval/MMLU）、人工评估、自动化指标（困惑度、胜率）以及业务场景回归测试四方面综合评估。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "你会在哪些场景被部署？"},
        {"from": "assistant", "value": "我可以被部署为 API 服务、智能客服、知识库问答助手或嵌入业务系统提供生成能力。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "你如何保证回答的准确性？"},
        {"from": "assistant", "value": "我通过高质量训练数据、偏好对齐抑制幻觉，并可在部署时接入检索增强（RAG）引用可靠资料。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "介绍一下你的训练平台"},
        {"from": "assistant", "value": "本平台提供数据处理、微调、对齐、压缩、评估与部署的一站式大模型训推能力，底层基于 MS-Swift 引擎。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "数据集质量重要吗？"},
        {"from": "assistant", "value": "非常重要。数据质量决定了模型能力上限，去重、清洗、配比与多样性检查是训练前的必备步骤。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "什么是过拟合？怎么避免？"},
        {"from": "assistant", "value": "过拟合指模型过度记忆训练样本导致泛化变差。可通过早停、增大训练 epoch、正则化、扩充数据来缓解。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "推理速度慢怎么办？"},
        {"from": "assistant", "value": "可以使用 vLLM 高性能推理框架，配合 KV Cache、连续批处理与量化（如 GPTQ/AWQ）显著提升吞吐。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "什么是量化压缩？"},
        {"from": "assistant", "value": "量化压缩将模型权重从 FP16/BF16 映射为低位宽表示（如 INT8/INT4），减小体积并加速推理，精度损失通常很小。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "你支持多轮对话吗？"},
        {"from": "assistant", "value": "支持。我会结合上下文理解你的追问，并保持话题连贯与指代一致。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "你如何处理敏感问题？"},
        {"from": "assistant", "value": "我会遵循安全对齐准则，拒答违法有害请求，并尽量提供安全、专业、中立的替代信息。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "什么是指令遵循能力？"},
        {"from": "assistant", "value": "指模型理解并严格执行用户指令（格式、约束、风格）的能力，通常通过指令微调数据强化。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "为什么需要人类反馈强化学习？"},
        {"from": "assistant", "value": "因为人类偏好难以用规则描述，RLHF/DPO 等方法让模型从偏好比较中学习，输出更符合人类期望。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "你会说哪些语言？"},
        {"from": "assistant", "value": "我主要使用中文与英文，也能处理少量其他语言的常见表达。"},
    ]},
    {"conversations": [
        {"from": "user", "value": "怎么开始训练一个自己的模型？"},
        {"from": "assistant", "value": "在平台上依次完成：上传/选择数据集 → 选择基座模型 → 配置微调参数 → 提交任务，训练完成后可一键部署评估。"},
    ]},
]

# 偏好数据里 rejected 回复的"劣化"模板（制造合理差距）
_BAD_TAILS = [
    "这个我不太清楚。",
    "抱歉，我无法回答这个问题。",
    "你可以去搜索引擎查一下。",
    "关于这个问题我还需要学习。",
]


def _log(msg: str) -> None:
    print(f"[demo-dataset] {msg}")


def _write_jsonl(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def _write_meta(meta_path: Path, meta: dict, count: int) -> None:
    payload = dict(meta)
    payload["sample_count"] = count
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    meta_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_jsonl(path: Path) -> List[dict]:
    rows: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _rows_to_turns(rows: List[dict]) -> List[List[dict]]:
    """把 conversations 行转成 [{role, content}, ...] 的多轮列表"""
    turns_list: List[List[dict]] = []
    for row in rows:
        conv = row.get("conversations") or row.get("messages") or []
        turns = [
            {"role": m.get("role") or ("user" if m.get("from") == "user" else "assistant"),
             "content": m.get("content") or m.get("value") or ""}
            for m in conv
            if (m.get("content") or m.get("value"))
        ]
        if len(turns) >= 2:
            turns_list.append(turns)
    return turns_list


def _dataset_complete(d: Path) -> bool:
    """目录内 train.jsonl 与 dataset.json 均存在且有效才算完整"""
    meta = d / "dataset.json"
    data = d / "train.jsonl"
    if not meta.is_file() or not data.is_file() or data.stat().st_size == 0:
        return False
    try:
        json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return True


def _build_sft_rows() -> List[dict]:
    return [{"messages": [
        {"role": m["from"], "content": m["value"]} for m in row["conversations"]
    ]} for row in SFT_SELF_COGNITION_ROWS]


def _build_preference_rows(sft_turns: List[List[dict]], samples: int) -> List[dict]:
    rng = random.Random(20260806)
    rows: List[dict] = []
    for turns in sft_turns[:samples]:
        chosen = [
            {"role": m["role"], "content": m["content"]} for m in turns
        ]
        rejected = [
            {"role": m["role"],
             "content": _BAD_TAILS[rng.randrange(len(_BAD_TAILS))] if m["role"] == "assistant"
             else m["content"]}
            for m in turns
        ]
        rows.append({"conversations": chosen, "chosen": chosen, "rejected": rejected})
    return rows


def _build_pretrain_rows(sft_turns: List[List[dict]], samples: int) -> List[dict]:
    rows: List[dict] = []
    for turns in sft_turns[:samples]:
        text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '助手'}：{m['content']}" for m in turns
        )
        rows.append({"text": text})
    return rows


def ensure_demo_datasets(root: Optional[Path], samples: int = 200) -> List[str]:
    """检查并补齐三个演示数据集文件，返回本次（重）生成的目录名列表（幂等）

    - 三个数据集目录任一缺 train.jsonl / dataset.json 即重新生成该目录
    - SFT 数据完整时从文件读取，缺失时本地生成；偏好/预训练由 SFT 轮次派生
    """
    if root is None:
        return []
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    samples = max(10, min(samples, 5000))

    sft_dir = root / SFT_DIR_NAME
    generated: List[str] = []

    # 1) SFT：缺失/损坏则重建
    if _dataset_complete(sft_dir):
        sft_rows = _read_jsonl(sft_dir / "train.jsonl")
    else:
        sft_rows = _build_sft_rows()
        _write_jsonl(sft_dir / "train.jsonl", sft_rows)
        _write_meta(sft_dir / "dataset.json", SFT_META, len(sft_rows))
        generated.append(SFT_DIR_NAME)
        _log(f"已生成 SFT 演示数据集: {sft_dir}（{len(sft_rows)} 条）")

    sft_turns = _rows_to_turns(sft_rows)
    if not sft_turns:
        # 文件存在但内容不可用（如空 turns），强制重建
        sft_rows = _build_sft_rows()
        _write_jsonl(sft_dir / "train.jsonl", sft_rows)
        _write_meta(sft_dir / "dataset.json", SFT_META, len(sft_rows))
        sft_turns = _rows_to_turns(sft_rows)
        if SFT_DIR_NAME not in generated:
            generated.append(SFT_DIR_NAME)
        _log(f"SFT 数据不可用，已重建: {sft_dir}")

    # 2) 偏好（DPO）
    pref_dir = root / PREF_DIR_NAME
    if not _dataset_complete(pref_dir):
        pref_rows = _build_preference_rows(sft_turns, samples)
        _write_jsonl(pref_dir / "train.jsonl", pref_rows)
        _write_meta(pref_dir / "dataset.json", PREF_META, len(pref_rows))
        generated.append(PREF_DIR_NAME)
        _log(f"已生成偏好演示数据集: {pref_dir}（{len(pref_rows)} 条）")

    # 3) 预训练（CPT）
    pt_dir = root / PT_DIR_NAME
    if not _dataset_complete(pt_dir):
        pt_rows = _build_pretrain_rows(sft_turns, samples)
        _write_jsonl(pt_dir / "train.jsonl", pt_rows)
        _write_meta(pt_dir / "dataset.json", PT_META, len(pt_rows))
        generated.append(PT_DIR_NAME)
        _log(f"已生成预训练演示数据集: {pt_dir}（{len(pt_rows)} 条）")

    return generated


__all__ = [
    "ensure_demo_datasets",
    "DEMO_DATASET_DIRS",
    "SFT_DIR_NAME",
    "PREF_DIR_NAME",
    "PT_DIR_NAME",
]
