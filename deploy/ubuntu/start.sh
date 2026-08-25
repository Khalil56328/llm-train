#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · Ubuntu 24.04 服务器启动脚本
# 用法：
#   bash deploy/ubuntu/start.sh              # 前台启动后端 API（前端由 FastAPI 托管）
#   bash deploy/ubuntu/start.sh --worker     # 同时启动 Celery Worker（任务在独立进程执行）
#   bash deploy/ubuntu/start.sh --port 9000  # 指定监听端口
#   bash deploy/ubuntu/start.sh --background # 后台运行（nohup，日志 backend/api.log，PID backend/api.pid）
#   bash deploy/ubuntu/start.sh --stop       # 停止后台 API
#   bash deploy/ubuntu/start.sh --restart    # 等价于 --stop 后启动
#
# 服务器长期运行推荐：bash deploy/ubuntu/install_systemd.sh（systemd 开机自启 + 崩溃自动拉起）
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  SUDO="sudo"
fi

# 优先使用 venv 中的 Python（init_env.sh 创建）；未初始化时回退系统 python3
PY="$PROJECT_ROOT/backend/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="python3"
  echo "    [WARN] 未找到 backend/.venv，使用系统 python3（请先执行 deploy/ubuntu/init_env.sh）"
fi

WITH_WORKER=0
PORT=8000
BACKGROUND=0
ACTION="start"
for arg in "$@"; do
  case "$arg" in
    --worker) WITH_WORKER=1 ;;
    --port=*) PORT="${arg#*=}" ;;
    --background) BACKGROUND=1 ;;
    --stop) ACTION="stop" ;;
    --restart) ACTION="restart" ;;
  esac
done

stop_api() {
  if [ -f "$PROJECT_ROOT/backend/api.pid" ]; then
    local pid
    pid="$(cat "$PROJECT_ROOT/backend/api.pid" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "==> 停止后台 API（PID $pid）"
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      kill -9 "$pid" 2>/dev/null || true
    else
      echo "==> API 未在运行（PID 文件过期）"
    fi
    rm -f "$PROJECT_ROOT/backend/api.pid"
  else
    echo "==> 未找到 backend/api.pid，跳过停止"
  fi
}

if [ "$ACTION" = "stop" ]; then
  stop_api
  exit 0
fi
if [ "$ACTION" = "restart" ]; then
  stop_api
  sleep 1
fi

# 确保依赖服务在运行（复用 Notebook 的辅助函数，兼容 systemd 服务器）
echo "==> 检查 MySQL / Redis"
# shellcheck disable=SC1091
source "$PROJECT_ROOT/deploy/notebook/lib_services.sh"
start_mysql || true
if ! wait_mysql 30; then
  echo "    [WARN] MySQL 未就绪，请检查：sudo systemctl status mysql"
fi
start_redis || true
if redis_alive; then
  echo "    Redis 已就绪"
else
  echo "    [WARN] Redis 未就绪（任务将降级为 API 进程内执行；--worker 模式需要 Redis）"
fi

# 可选：Celery Worker（需要 Redis）
if [ "$WITH_WORKER" -eq 1 ]; then
  echo "==> 启动 Celery Worker"
  (cd backend && nohup "$PY" -m celery -A app.tasks.worker:celery_app worker --loglevel=info \
      > "$PROJECT_ROOT/backend/celery.log" 2>&1 &)
  echo "    Worker 日志：backend/celery.log"
fi

echo "==> 启动后端 API（:${PORT}，前端由 FastAPI 托管）"
cd backend
if [ "$BACKGROUND" -eq 1 ]; then
  nohup "$PY" -m uvicorn main:app --host 0.0.0.0 --port "$PORT" \
      > "$PROJECT_ROOT/backend/api.log" 2>&1 &
  echo "$!" > "$PROJECT_ROOT/backend/api.pid"
  sleep 2
  if kill -0 "$(cat "$PROJECT_ROOT/backend/api.pid")" 2>/dev/null; then
    echo "    API 已在后台启动：PID $(cat "$PROJECT_ROOT/backend/api.pid")"
    echo "    日志：backend/api.log；停止：bash deploy/ubuntu/start.sh --stop"
  else
    echo "    [ERROR] API 启动失败，请查看 backend/api.log"
    exit 1
  fi
else
  exec "$PY" -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
fi
