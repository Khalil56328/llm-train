#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · ModelScope 模型/数据集下载助手（Notebook 与 Ubuntu 服务器通用）
#
# 模型下载完成后会自动录入模型库（模拟「我的模型库 → 创建模型 → 上传模型文件」
# 页面逻辑，见 deploy/common/seed_model_record.py）：插入 models / model_versions /
# model_files 记录，storage_path 与 file_path 指向真实下载的模型文件，
# 「我的模型库 / 模型库广场」立即可见。数据集仍为下载后手动指向 storage_path。
#
# 用法：
#   bash deploy/common/download_models.sh --model Qwen/Qwen2.5-0.5B-Instruct
#   bash deploy/common/download_models.sh --model Qwen/Qwen2.5-0.5B-Instruct --dir models/qwen/qwen2.5-0.5b-instruct
#   bash deploy/common/download_models.sh --dataset swift/self-cognition  --dir datasets/self-cognition
#   bash deploy/common/download_models.sh --model A --model B            # 一次下载多个
#
# 参数：
#   --model <id>    ModelScope 模型 ID（如 Qwen/Qwen2.5-0.5B-Instruct），可重复
#   --dataset <id>  ModelScope 数据集 ID（如 swift/self-cognition），可重复
#   --dir <path>    相对 backend/workspace/ 的落盘目录；默认
#                   models/<模型名小写> / datasets/<数据集名小写>
#   --root <path>   自定义落盘根目录（默认 backend/workspace）
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Python 解释器：优先 backend/.venv（Ubuntu 24.04 依赖装在 venv，系统 python3 受 PEP 668
# 限制无法 pip 安装 modelscope）；Notebook 环境无 venv 时回退系统 python3（已预装依赖）
VENV_PY="$PROJECT_ROOT/backend/.venv/bin/python"
if [ -x "$VENV_PY" ]; then
  PY_BIN="$VENV_PY"
else
  PY_BIN="python3"
  echo "    [INFO] 未找到 backend/.venv，使用系统 python3。"
  echo "           Ubuntu 24.04 环境请先执行 bash deploy/ubuntu/init_env.sh（PEP 668 下"
  echo "           系统 python3 无法 pip 安装 modelscope，依赖装在 backend/.venv 内）。"
fi

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

# 确保 modelscope 可用（Notebook 镜像已预装；Ubuntu 由 backend/requirements.txt 随 venv 安装；
# 缺失时补装，优先用 venv 的 pip）
if ! "$PY_BIN" -c "import modelscope" 2>/dev/null; then
  echo "==> 未检测到 modelscope，自动安装..."
  if ! "$PY_BIN" -m pip install -q modelscope; then
    echo "[ERROR] modelscope 安装失败（$PY_BIN）。"
    echo "        Ubuntu 24.04 请先执行 bash deploy/ubuntu/init_env.sh（PEP 668 下依赖须装在 backend/.venv）。"
    exit 1
  fi
fi
if ! command -v modelscope >/dev/null 2>&1; then
  # modelscope 新版可能只提供 python -m modelscope 入口
  if ! "$PY_BIN" -m modelscope --help >/dev/null 2>&1; then
    echo "[ERROR] modelscope CLI 不可用，请确认安装成功（$PY_BIN -m pip install modelscope）"
    exit 1
  fi
  MS_CLI=("$PY_BIN" -m modelscope)
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
  echo "    真实路径（storage_path）：$abs_dir"
}

# 录入模型库：模拟「我的模型库 → 创建模型 → 上传模型文件」页面逻辑
# （models / model_versions / model_files 三表，文件指向真实下载路径）。
# 幂等：已按 storage_path 录入过的模型自动跳过。失败不阻断下载流程。
register_model_record() {
  local id="$1" rel_dir="$2"
  echo ""
  echo "==> 录入模型库（模拟页面新增模型 + 上传文件）..."
  if "$PY_BIN" "$PROJECT_ROOT/deploy/common/seed_model_record.py" \
      --model "$id" --root "$ROOT_DIR" --dir "$rel_dir"; then
    echo "    模型已录入「我的模型库 / 模型库广场」"
  else
    echo "    [WARN] 模型录入失败（MySQL 未就绪或依赖缺失？可稍后手动执行："
    echo "           $PY_BIN $PROJECT_ROOT/deploy/common/seed_model_record.py --model $id --root $ROOT_DIR --dir $rel_dir）"
  fi
}

for m in "${MODELS[@]}"; do
  name="$(basename "$m" | tr '[:upper:]' '[:lower:]')"
  rel_dir="${CUSTOM_DIR:-models/$name}"
  download_one "model" "$m" "$rel_dir"
  register_model_record "$m" "$rel_dir"
done
for d in "${DATASETS[@]}"; do
  name="$(basename "$d" | tr '[:upper:]' '[:lower:]')"
  download_one "dataset" "$d" "${CUSTOM_DIR:-datasets/$name}"
done

echo ""
echo "============================================================"
if [ "${#MODELS[@]}" -gt 0 ]; then
  echo "模型已下载并自动录入模型库（我的模型库 / 模型库广场可见，文件指向真实路径）。"
fi
if [ "${#DATASETS[@]}" -gt 0 ]; then
  echo "数据集已下载。下一步：在平台「数据集管理」编辑 storage_path，"
  echo "改为上面打印的绝对路径，然后提交训练任务（TRAIN_EXECUTION_MODE=auto 即真实执行）。"
fi
echo "============================================================"
