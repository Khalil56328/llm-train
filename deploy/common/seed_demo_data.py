#!/usr/bin/env python3
"""生成演示数据集（SFT / 偏好 / 预训练文本），供训练向导开箱可选。

用法（项目根目录执行）：
  python3 deploy/common/seed_demo_data.py [--root backend/workspace] [--samples 200] [--force]

生成到 <root>/datasets/ 下三个目录，每个目录含 dataset.json 元信息，
后端启动时由 DatasetSeedService 扫描录入数据集管理（幂等）：
  sft_self_cognition/  对话式 SFT 数据集（本地生成标准 swift 对话格式）
  preference_demo/     偏好对数据集（由 SFT 样本生成的 chosen/rejected 对，DPO/KTO/ORPO/SimPO 演示）
  pretrain_demo/       预训练文本数据集（{"text": ...}，swift pt 演示）

说明：三个演示数据集全部在本地生成，不再依赖从 ModelScope 网络下载
（swift/self-cognition 网络下载易因网络/LFS 占位文件产生空 jsonl 或缺失文件，
且下载目录无 dataset.json 导致后台无法录入）。所有目录统一写 dataset.json，
含 category（数据集分类）字段，后台可正常录入并在前端正确展示。
"""
import argparse
import json
import random
import sys
from pathlib import Path

SFT_DIR_NAME = "sft_self_cognition"
PREF_DIR_NAME = "preference_demo"
PT_DIR_NAME = "pretrain_demo"

# 数据集分类（对应前端「数据集分类」下拉：文本生成/图像生成/代码生成）
CATEGORY_TEXT_GEN = "文本生成"


def log(msg: str) -> None:
    print(f"[seed-demo] {msg}", flush=True)


# 内置演示语料（与 swift/self-cognition 风格一致的自我介绍对话样本）
_INTRO_PAIRS = [
    ("你好", "你好！我是本平台的 AI 助手，很高兴为你服务。你可以叫我小灵，有什么可以帮你的吗？"),
    ("你是谁", "我是 LLM 训推平台内置的演示模型助手，基于开源大模型微调而成，能够回答日常问题、辅助写作和编程。"),
    ("介绍一下你自己", "我是一款本地部署的对话助手，具备文本理解、内容生成和编程辅助能力。我的底座模型经过了针对性微调。"),
    ("你能做什么", "我可以帮你解答问题、撰写文案、生成代码、整理信息。请告诉我你的具体需求，我会尽力协助。"),
    ("今天天气怎么样", "抱歉，我暂时无法获取实时天气信息。建议你查看当地气象服务或打开天气应用获取最新预报。"),
    ("如何快速学习编程", "可以从 Python 入门：先掌握基础语法，再通过小项目练习，最后结合数据结构与算法循序渐进。关键是坚持实践。"),
    ("推荐一本书", "如果你对人工智能感兴趣，推荐阅读《深度学习》和《动手学深度学习》，理论与实践结合，非常适合入门。"),
    ("什么是机器学习", "机器学习是让计算机从数据中自动学习规律的一门技术，通过算法拟合数据分布，从而对未知样本进行预测。"),
    ("写一段 Python 代码", "可以。例如计算斐波那契数列：\\ndef fib(n):\\n    a, b = 0, 1\\n    for _ in range(n):\\n        a, b = b, a + b\\n    return a\\n\\nprint(fib(10))"),
    ("谢谢你", "不客气，能帮到你是我的荣幸。如果还有其他问题，随时告诉我哦！"),
    ("帮我写一封感谢信", "好的，参考如下：\\n\\n尊敬的张老师：\\n\\n感谢您在我学习期间给予的悉心指导和无私帮助，让我受益匪浅。值此之际，谨向您致以诚挚的谢意。\\n\\n此致\\n敬礼"),
    ("什么是大语言模型", "大语言模型是基于海量文本预训练的神经网络模型，参数量通常达数十亿到数千亿，擅长自然语言理解与生成。"),
]


def _to_turns(user_msg: str, asst_msg: str) -> list:
    """将一问一答转成统一的 turns 列表（供偏好/预训练复用）"""
    return [
        {"role": "user", "content": user_msg.strip()},
        {"role": "assistant", "content": asst_msg.strip()},
    ]


def _rows_to_turns(rows: list) -> list:
    """将 swift 对话行解析成 turns 列表（兼容 conversations 与 messages 两种格式）"""
    turns_list = []
    for row in rows:
        turns = []
        for msg in (row.get("conversations") or row.get("messages") or []):
            if not isinstance(msg, dict):
                continue
            role = msg.get("from") or msg.get("role") or ""
            content = msg.get("value") or msg.get("content") or ""
            role = {"human": "user", "qwen": "assistant", "assistant": "assistant"}.get(role, role)
            if role in ("user", "assistant") and content:
                turns.append({"role": role, "content": str(content).strip()})
        if len(turns) >= 2:
            turns_list.append(turns)
    return turns_list


def build_sft(sft_dir: Path, force: bool) -> list:
    """本地生成 SFT 演示数据集（swift 对话格式），返回 turns 列表供偏好/预训练复用"""
    out_path = sft_dir / "train.jsonl"
    if sft_dir.exists() and not force and out_path.exists() and out_path.stat().st_size > 0:
        log(f"SFT 数据已存在，跳过生成: {sft_dir}")
        rows = []
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return _rows_to_turns(rows)
    sft_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20240826)
    rows = []
    for user_msg, asst_msg in _INTRO_PAIRS:
        rows.append(
            {
                "conversations": [
                    {"from": "human", "value": user_msg},
                    {"from": "assistant", "value": asst_msg},
                ]
            }
        )
    # 增加一些变体（随机拼接一问一答），使样本更丰富
    pool = [p for p in _INTRO_PAIRS]
    for _ in range(8):
        user_msg, asst_msg = rng.choice(pool)
        rows.append(
            {
                "conversations": [
                    {"from": "human", "value": user_msg},
                    {"from": "assistant", "value": asst_msg},
                ]
            }
        )
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    write_dataset_meta(
        sft_dir,
        name="self-cognition 演示 SFT 数据集",
        data_type="SFT",
        category=CATEGORY_TEXT_GEN,
        description="本地生成的对话式 SFT 数据集（swift 格式），用于微调训练演示",
        sample_count=len(rows),
    )
    log(f"已生成 SFT 数据集: {out_path}（{len(rows)} 条）")
    return _rows_to_turns(rows)


def write_dataset_meta(ds_dir: Path, name: str, data_type: str, category: str,
                       description: str, sample_count: int) -> None:
    ds_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "name": name,
        "type": "training",
        "data_type": data_type,
        "category": category,
        "description": description,
        "sample_count": sample_count,
    }
    (ds_dir / "dataset.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"已生成元信息: {ds_dir / 'dataset.json'}（{sample_count} 条）")


def build_preference(sft_turns: list, pref_dir: Path, samples: int, force: bool) -> None:
    """由 SFT 对话样本生成 chosen/rejected 偏好对（演示用，rejected 为截断/敷衍回复）"""
    if pref_dir.exists() and not force and (pref_dir / "train.jsonl").exists() \
            and (pref_dir / "train.jsonl").stat().st_size > 0:
        log(f"偏好数据集已存在，跳过: {pref_dir}")
        return
    if not sft_turns:
        raise RuntimeError("SFT 数据缺失，无法生成偏好数据集")
    pref_dir.mkdir(parents=True, exist_ok=True)
    out_path = pref_dir / "train.jsonl"
    n = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for turns in sft_turns[:samples]:
            if len(turns) < 2:
                continue
            user_msg, assistant_msg = turns[0], turns[1]
            rejected_content = "抱歉，我暂时无法回答这个问题。" if len(assistant_msg["content"]) > 10 \
                else assistant_msg["content"][: max(1, len(assistant_msg["content"]) // 2)]
            row = {
                "chosen": [user_msg, assistant_msg],
                "rejected": [user_msg, {"role": "assistant", "content": rejected_content}],
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    write_dataset_meta(
        pref_dir, "preference_demo 偏好对齐演示数据集", "DPO",
        CATEGORY_TEXT_GEN,
        "由 self-cognition 生成的偏好对（chosen/rejected），用于 DPO/KTO/ORPO/SimPO 对齐演示",
        n,
    )


def build_pretrain(sft_turns: list, pt_dir: Path, samples: int, force: bool) -> None:
    """由 SFT 对话样本生成预训练文本数据（{"text": ...}，swift pt 格式）"""
    if pt_dir.exists() and not force and (pt_dir / "train.jsonl").exists() \
            and (pt_dir / "train.jsonl").stat().st_size > 0:
        log(f"预训练数据集已存在，跳过: {pt_dir}")
        return
    if not sft_turns:
        raise RuntimeError("SFT 数据缺失，无法生成预训练数据集")
    pt_dir.mkdir(parents=True, exist_ok=True)
    out_path = pt_dir / "train.jsonl"
    n = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for turns in sft_turns[:samples]:
            text = "\n".join(f"{t['role']}: {t['content']}" for t in turns)
            out.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
            n += 1
    write_dataset_meta(
        pt_dir, "pretrain_demo 预训练文本演示数据集", "CPT",
        CATEGORY_TEXT_GEN,
        "由 self-cognition 生成的纯文本数据（{\"text\": ...}），用于 swift pt 预训练演示",
        n,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 LLM 训推平台演示数据集")
    parser.add_argument("--root", default="backend/workspace",
                        help="训练工作目录（默认 backend/workspace，相对当前目录解析）")
    parser.add_argument("--samples", type=int, default=200, help="偏好/预训练演示数据最大样本数（默认 200）")
    parser.add_argument("--force", action="store_true", help="已存在时强制重新生成")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_absolute():
        root = Path.cwd() / root
    datasets_dir = root / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    sft_dir = datasets_dir / SFT_DIR_NAME
    sft_turns = build_sft(sft_dir, args.force)

    samples = max(10, min(args.samples, 5000))
    build_preference(sft_turns, datasets_dir / PREF_DIR_NAME, samples, args.force)
    build_pretrain(sft_turns, datasets_dir / PT_DIR_NAME, samples, args.force)

    log("完成。生成的数据集目录：")
    for sub in sorted(datasets_dir.iterdir()):
        if (sub / "dataset.json").exists():
            log(f"  - {sub}（{sub / 'dataset.json'}）")
    log("后端启动时会自动录入「数据集管理」（is_public=true，训练向导可直接选择）。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"[seed-demo][ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
