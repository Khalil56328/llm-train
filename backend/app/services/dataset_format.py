"""数据集格式处理工具：CSV → JSONL 自动转换

ModelScope / HuggingFace 上下载的许多数据集仓库是 CSV 或分片 CSV 的
分发形态，而 MS-Swift 训练引擎的标准数据集格式是 JSONL（每行一条样本，
自带字段名）。本模块负责把通用表格字段自动对齐到 MS-Swift 标准字段，
输出符合主流大模型训练要求的 JSONL 文件。

支持的通用字段映射（按列名大小写不敏感、去空白后匹配）：
- 指令/输入侧：instruction, prompt, query, question, input, src, source, 指令, 问题
- 输出侧：output, response, answer, reply, completion, 回答, 输出
- 对话/续写/预训练：text, content, conversations
- 系统提示（可选）：system
- 历史对话（可选）：history, messages
"""
from __future__ import annotations

import csv
import io
import json
from typing import Dict, List

# 列名 → 归一化字段 的映射表（键为小写去空白后的列名）
_ALIAS_MAP: Dict[str, str] = {
    # 指令侧
    "instruction": "instruction",
    "prompt": "instruction",
    "query": "instruction",
    "question": "instruction",
    "input": "instruction",
    "src": "instruction",
    "source": "instruction",
    "中文指令": "instruction",
    "指令": "instruction",
    "问题": "instruction",
    "题目": "instruction",
    # 输出侧
    "output": "output",
    "response": "output",
    "answer": "output",
    "reply": "output",
    "completion": "output",
    "target": "output",
    "回答": "output",
    "输出": "output",
    "答案": "output",
    # 续写/预训练/通用文本
    "text": "text",
    "content": "text",
    "corpus": "text",
    "正文": "text",
    "文本": "text",
    # 对话（多轮）
    "conversations": "conversations",
    "messages": "conversations",
    "dialogue": "conversations",
    "对话": "conversations",
    # 可选辅助
    "system": "system",
    "系统提示": "system",
    "history": "history",
    "历史": "history",
}


def _norm_col(col: str) -> str:
    return col.strip().lower()


def _guess_columns(header: List[str]) -> Dict[str, str]:
    """根据表头猜测列到归一化字段的映射。

    返回 {归一化字段: 原始列名}；找不到任何可识别列时返回空 dict。
    """
    mapping: Dict[str, str] = {}
    for col in header:
        key = _norm_col(col)
        field = _ALIAS_MAP.get(key)
        if field and field not in mapping:
            mapping[field] = col
    return mapping


def csv_to_jsonl(csv_bytes: bytes, source_name: str = "") -> bytes:
    """把 CSV 内容转换为 JSONL 内容（UTF-8）。

    - 自动用 UTF-8-SIG / GBK / GB18030 尝试解码，兼容常见编码
    - 自动对齐字段映射；无法识别的数据集抛 ValueError
    - 输出字段优先按 MS-Swift 语义：
        SFT: instruction/output（存在 conversations 时输出 conversations）
        CPT: text
    """
    text = _decode(csv_bytes)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 文件为空或没有表头，无法转换")

    mapping = _guess_columns(reader.fieldnames)
    if not mapping:
        raise ValueError(
            "无法识别 CSV 列，请确保包含以下字段之一：instruction/output、"
            "prompt/response、query/answer、input/output、text、content 或 conversations"
        )

    records: List[Dict] = []
    for row in reader:
        record = {}
        for field, col in mapping.items():
            value = (row.get(col) or "").strip()
            if value:
                record[field] = value
        if not record:
            continue
        # 仅保留已映射的非空字段，避免混入未识别的多余列
        records.append(record)

    if not records:
        raise ValueError("CSV 中没有可转换的有效数据行")

    return b"\n".join(
        json.dumps(r, ensure_ascii=False).encode("utf-8") for r in records
    ) + b"\n"


def _decode(data: bytes) -> str:
    """按 UTF-8 / UTF-8-SIG / GB18030 依次尝试解码"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError("CSV 文件编码无法识别（仅支持 UTF-8 / GBK）")
