#!/usr/bin/env python3
"""生成演示数据集（SFT / 偏好 / 预训练文本），供训练向导开箱可选。

用法（项目根目录执行）：
  python3 deploy/common/seed_demo_data.py [--root backend/workspace] [--samples 200] [--force]

生成到 <root>/datasets/ 下三个目录，每个目录含 dataset.json 元信息，
后端启动时由 DatasetSeedService 扫描录入数据集管理（幂等）：
  sft_self_cognition/  对话式 SFT 数据集（ModelScope 下载 swift/self-cognition）
  preference_demo/     偏好对数据集（由 SFT 样本生成的 chosen/rejected 对，DPO/KTO/ORPO/SimPO 演示）
  pretrain_demo/       预训练文本数据集（{"text": ...}，swift pt 演示）

依赖：modelscope（下载 self-cognition 用，缺失时自动安装）；失败不影响初始化流程
（init_env.sh 中已用 || WARN 兜底，可稍后手动重跑）。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SFT_DS_ID = "swift/self-cognition"
SFT_DIR_NAME = "sft_self_cognition"
PREF_DIR_NAME = "preference_demo"
PT_DIR_NAME = "pretrain_demo"


def log(msg: str) -> None:
    print(f"[seed-demo] {msg}", flush=True)


def run(cmd, cwd=None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def ensure_modelscope() -> None:
    try:
        import modelscope  # noqa: F401
        return
    except ImportError:
        pass
    log("未检测到 modelscope，自动安装...")
    run([sys.executable, "-m", "pip", "install", "-q", "modelscope"])


def download_sft(sft_dir: Path) -> None:
    """下载 swift/self-cognition 到 sft_dir（目录非空则跳过）"""
    if any(sft_dir.glob("*.jsonl")):
        log(f"SFT 数据已存在，跳过下载: {sft_dir}")
        return
    sft_dir.mkdir(parents=True, exist_ok=True)
    log(f"下载 SFT 演示数据集 {SFT_DS_ID} -> {sft_dir}（约几 MB，视网速而定）")
    try:
        run([sys.executable, "-m", "modelscope", "download", "--dataset", SFT_DS_ID,
             "--local_dir", str(sft_dir)])
    except subprocess.CalledProcessError:
        run(["modelscope", "download", "--dataset", SFT_DS_ID, "--local_dir", str(sft_dir)])
    if not any(sft_dir.glob("*.jsonl")):
        raise RuntimeError(f"SFT 数据集下载后未找到 jsonl 文件: {sft_dir}")


def iter_conversations(jsonl_path: Path, limit: int):
    """逐行读取对话数据，兼容 ms-swift 的 conversations(from/value) 与 messages(role/content) 两种格式"""
    count = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
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
                yield turns
                count += 1
                if count >= limit:
                    return


def write_dataset_meta(ds_dir: Path, name: str, data_type: str, description: str, sample_count: int) -> None:
    ds_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "name": name,
        "type": "training",
        "data_type": data_type,
        "description": description,
        "sample_count": sample_count,
    }
    (ds_dir / "dataset.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"已生成元信息: {ds_dir / 'dataset.json'}（{sample_count} 条）")


def build_preference(sft_dir: Path, pref_dir: Path, samples: int, force: bool) -> None:
    """由 SFT 对话样本生成 chosen/rejected 偏好对（演示用，rejected 为截断/敷衍回复）"""
    if pref_dir.exists() and not force and (pref_dir / "train.jsonl").exists():
        log(f"偏好数据集已存在，跳过: {pref_dir}")
        return
    sft_file = next(sft_dir.glob("*.jsonl"), None)
    if not sft_file:
        raise RuntimeError("SFT 数据缺失，无法生成偏好数据集")
    pref_dir.mkdir(parents=True, exist_ok=True)
    out_path = pref_dir / "train.jsonl"
    n = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for turns in iter_conversations(sft_file, samples):
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
        "由 self-cognition 生成的偏好对（chosen/rejected），用于 DPO/KTO/ORPO/SimPO 对齐演示",
        n,
    )


def build_pretrain(sft_dir: Path, pt_dir: Path, samples: int, force: bool) -> None:
    """由 SFT 对话样本生成预训练文本数据（{"text": ...}，swift pt 格式）"""
    if pt_dir.exists() and not force and (pt_dir / "train.jsonl").exists():
        log(f"预训练数据集已存在，跳过: {pt_dir}")
        return
    sft_file = next(sft_dir.glob("*.jsonl"), None)
    if not sft_file:
        raise RuntimeError("SFT 数据缺失，无法生成预训练数据集")
    pt_dir.mkdir(parents=True, exist_ok=True)
    out_path = pt_dir / "train.jsonl"
    n = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for turns in iter_conversations(sft_file, samples):
            text = "\n".join(f"{t['role']}: {t['content']}" for t in turns)
            out.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
            n += 1
    write_dataset_meta(
        pt_dir, "pretrain_demo 预训练文本演示数据集", "CPT",
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

    ensure_modelscope()
    sft_dir = datasets_dir / SFT_DIR_NAME
    download_sft(sft_dir)

    samples = max(10, min(args.samples, 5000))
    build_preference(sft_dir, datasets_dir / PREF_DIR_NAME, samples, args.force)
    build_pretrain(sft_dir, datasets_dir / PT_DIR_NAME, samples, args.force)

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
