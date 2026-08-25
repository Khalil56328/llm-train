#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · 数据备份助手（Notebook 实例释放即丢数据，务必定期备份）
#
# 备份内容：
#   1. MySQL 数据库 llm_train 全量 dump（backups/llm_train_<时间戳>.sql）
#   2. 训练工作目录 + 本地存储（backups/data_<时间戳>.tar.gz）：
#      backend/workspace（模型/数据集/训练产物）+ backend/storage（上传文件/评测报告）
#
# 用法：
#   bash deploy/notebook/backup.sh                    # 备份到 backend/backups/
#   bash deploy/notebook/backup.sh --no-data          # 仅备份数据库
#   bash deploy/notebook/backup.sh --out /path/to/dir # 指定备份目录
#
# 备份后务必把 backups/ 下载到本地或上传到 ModelScope 数据集仓库中转：
#   modelscope upload --dataset <你的账号>/<仓库名> backend/backups backups
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

WITH_DATA=1
OUT_DIR="$PROJECT_ROOT/backend/backups"
while [ $# -gt 0 ]; do
  case "$1" in
    --no-data) WITH_DATA=0 ;;
    --out)     OUT_DIR="$2"; shift 2 ;;
    -h|--help) echo "用法: bash deploy/notebook/backup.sh [--no-data] [--out <dir>]"; exit 0 ;;
    *) echo "[ERROR] 未知参数: $1"; exit 1 ;;
  esac
done

if command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
fi

mkdir -p "$OUT_DIR"
TS="$(date +%Y%m%d_%H%M%S)"

# 从 backend/.env 解析数据库连接（用户名/密码/库名），密码含特殊字符时自行 URL 解码
ENV_FILE="$PROJECT_ROOT/backend/.env"
DB_USER="llm_train"
DB_PASS="llm_train_2026"
DB_NAME="llm_train"
if [ -f "$ENV_FILE" ]; then
  DB_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  if [ -n "$DB_URL" ]; then
    DB_USER="$(printf '%s' "$DB_URL" | sed -E 's#^[a-z+]+://([^:]+):([^@]+)@.*#\1#')"
    DB_PASS="$(printf '%s' "$DB_URL" | sed -E 's#^[a-z+]+://([^:]+):([^@]+)@.*#\2#')"
    DB_NAME="$(printf '%s' "$DB_URL" | sed -E 's#^.*/([^/?]+)(\?.*)?$#\1#')"
  fi
fi

# 密码 URL 编码反转义（%40 → @ 等）
DB_PASS="$(printf '%s' "$DB_PASS" | sed -e 's/%40/@/g' -e 's/%21/!/g' -e 's/%23/#/g' -e 's/%24/$/g' -e 's/%25/%/g' -e 's/%26/\&/g')"

echo "==> 备份数据库 $DB_NAME -> $OUT_DIR/llm_train_$TS.sql"
# 使用本机 root（auth_socket / 无密码）走 socket 备份最稳妥；失败回退应用账号 TCP
if $SUDO mysqldump --single-transaction --skip-lock-tables "$DB_NAME" > "$OUT_DIR/llm_train_$TS.sql" 2>/dev/null; then
  :
elif mysqldump --single-transaction -h 127.0.0.1 -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" > "$OUT_DIR/llm_train_$TS.sql" 2>/dev/null; then
  :
else
  echo "    [WARN] 数据库备份失败：请确认 MySQL 已启动，或手动执行"
  echo "           mysqldump --single-transaction -h 127.0.0.1 -u llm_train -p llm_train > llm_train.sql"
  rm -f "$OUT_DIR/llm_train_$TS.sql"
fi

if [ "$WITH_DATA" -eq 1 ]; then
  echo "==> 打包工作目录与存储 -> $OUT_DIR/data_$TS.tar.gz"
  TAR_TARGETS=()
  [ -d "$PROJECT_ROOT/backend/workspace" ] && TAR_TARGETS+=(backend/workspace)
  [ -d "$PROJECT_ROOT/backend/storage" ] && TAR_TARGETS+=(backend/storage)
  if [ "${#TAR_TARGETS[@]}" -gt 0 ]; then
    tar czf "$OUT_DIR/data_$TS.tar.gz" "${TAR_TARGETS[@]}"
  else
    echo "    [WARN] backend/workspace 与 backend/storage 均不存在，跳过数据打包"
  fi
fi

echo ""
echo "============================================================"
echo "备份完成：$OUT_DIR"
ls -lh "$OUT_DIR"
echo "------------------------------------------------------------"
echo "请立即把 backups/ 目录下载到本地，或上传到 ModelScope 数据集仓库："
echo "  pip install modelscope"
echo "  modelscope upload --dataset <你的账号>/<仓库名> backend/backups backups"
echo "============================================================"
