#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · ModelScope 模型/数据集下载助手（Notebook 与 Ubuntu 服务器通用）
#
# 真实训练/推理要求模型与数据集路径真实存在（平台默认模型由部署脚本下载后自动录入，
# 其余模型/数据集需先下载再把 storage_path 指向真实路径）。
# 本脚本用 modelscope CLI 把模型/数据集下载到 backend/workspace 下，并打印
# 应填入平台「模型管理 / 数据集管理 → storage_path」的绝对路径。
#
# 用法：
#   bash deploy/notebook/download_models.sh --model Qwen/Qwen2.5-7B-Instruct
#   bash deploy/notebook/download_models.sh --model Qwen/Qwen2.5-7B-Instruct --dir models/qwen/qwen2.5-7b-instruct
#   bash deploy/notebook/download_models.sh --dataset swift/self-cognition  --dir datasets/self-cognition
#   bash deploy/notebook/download_models.sh --model A --model B            # 一次下载多个
#
# 参数：
#   --model <id>    ModelScope 模型 ID（如 Qwen/Qwen2.5-7B-Instruct），可重复
#   --dataset <id>  ModelScope 数据集 ID（如 swift/self-cognition），可重复
#   --dir <path>    相对 backend/workspace/ 的落盘目录；默认
#                   models/<模型名小写> / datasets/<数据集名小写>
#   --root <path>   自定义落盘根目录（默认 backend/workspace）
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

ROOT_DIR="$PROJECT_ROOT/backend/workspace"
declare -a MODELS=()
declare -a DATASETS=()
CUSTOM_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --model)   MODELS+=("$2"); shift 2 ;;
    --dataset) DATASETS+=("$2"); shift 2 ;;
    --dir)     CUSTOM_DIR="$2"; shift 2 ;;
    --root)    ROOT_DIR="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,30p' "$0" | grep -E '^#|^用法' | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "[ERROR] 未知参数: $1（--help 查看用法）"; exit 1 ;;
  esac
done

if [ "${#MODELS[@]}" -eq 0 ] && [ "${#DATASETS[@]}" -eq 0 ]; then
  echo "[ERROR] 至少需要 --model 或 --dataset 参数（--help 查看用法）"
  exit 1
fi

# 确保 modelscope 可用（Notebook 镜像已预装；缺失时补装）
if ! python3 -c "import modelscope" 2>/dev/null; then
  echo "==> 未检测到 modelscope，自动安装..."
  python3 -m pip install -q modelscope
fi
if ! command -v modelscope >/dev/null 2>&1; then
  # modelscope 新版可能只提供 python -m modelscope 入口
  if ! python3 -m modelscope --help >/dev/null 2>&1; then
    echo "[ERROR] modelscope CLI 不可用，请确认安装成功（python3 -m pip install modelscope）"
    exit 1
  fi
  MS_CLI=(python3 -m modelscope)
else
  MS_CLI=(modelscope)
fi

mkdir -p "$ROOT_DIR"

download_one() {
  local kind="$1" id="$2" rel_dir="$3" abs_dir
  abs_dir="$ROOT_DIR/$rel_dir"
  echo ""
  echo "==> 下载 $kind: $id  ->  $abs_dir"
  if [ -d "$abs_dir" ] && [ -n "$(ls -A "$abs_dir" 2>/dev/null)" ]; then
    echo "    目录已存在且非空，跳过下载（如需重新下载请先删除该目录）"
  else
    mkdir -p "$abs_dir"
    if [ "$kind" = "model" ]; then
      "${MS_CLI[@]}" download --model "$id" --local_dir "$abs_dir"
    else
      "${MS_CLI[@]}" download --dataset "$id" --local_dir "$abs_dir"
    fi
  fi
  echo ""
  echo "    [填写] 平台「$kind 管理」中把该 $kind 的 storage_path 设为："
  echo "    $abs_dir"
}

for m in "${MODELS[@]}"; do
  name="$(basename "$m" | tr '[:upper:]' '[:lower:]')"
  download_one "model" "$m" "${CUSTOM_DIR:-models/$name}"
done
for d in "${DATASETS[@]}"; do
  name="$(basename "$d" | tr '[:upper:]' '[:lower:]')"
  download_one "dataset" "$d" "${CUSTOM_DIR:-datasets/$name}"
done

echo ""
echo "============================================================"
echo "下载完成。下一步：在平台「模型管理/数据集管理」编辑 storage_path，"
echo "改为上面打印的绝对路径，然后提交训练任务（TRAIN_EXECUTION_MODE=auto 即真实执行）。"
echo "============================================================"
