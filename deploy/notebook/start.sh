#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · ModelScope Notebook 一键启动脚本
# 用法：
#   bash deploy/notebook/start.sh              # 前台启动后端 API（前端由 FastAPI 托管）
#   bash deploy/notebook/start.sh --worker     # 同时启动 Celery Worker（任务在独立进程执行）
#   bash deploy/notebook/start.sh --port 9000  # 指定监听端口（配合 Notebook 端口映射）
#   bash deploy/notebook/start.sh --background # 后台运行（nohup，日志 backend/api.log，PID backend/api.pid）
#   bash deploy/notebook/start.sh --stop       # 停止后台 API（读 backend/api.pid）
#   bash deploy/notebook/start.sh --restart    # 等价于 --stop 后前台/后台启动
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

if command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
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

# 停止后台 API（幂等；只停 API 进程，Worker 由 celery 进程自行管理）
stop_api() {
  if [ -f "$PROJECT_ROOT/backend/api.pid" ]; then
    local pid
    pid="$(cat "$PROJECT_ROOT/backend/api.pid" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "==> 停止后台 API（PID $pid）"
      kill "$pid" 2>/dev/null || true
      # 等待进程退出（最多 10s）
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

# 释放指定端口：按端口检测并停止占用进程。
# 用于兜底 pid 文件不可靠的场景（如前台启动未写 pid、PID 文件丢失、uvicorn --reload 子进程残留），
# 避免启动时报 [Errno 98] address already in use。
free_port() {
  local port="$1"
  if ! command -v fuser >/dev/null 2>&1; then
    echo "    [WARN] 未找到 fuser，跳过端口清理（Notebook 容器请先 apt-get install -y psmisc）"
    return 0
  fi
  if ! fuser "$port/tcp" >/dev/null 2>&1; then
    return 0  # 端口空闲
  fi
  echo "==> 端口 :${port} 被占用，正在停止占用进程..."
  fuser -k -TERM "$port/tcp" 2>/dev/null || true
  for _ in $(seq 1 10); do
    if ! fuser "$port/tcp" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if fuser "$port/tcp" >/dev/null 2>&1; then
    echo "    [WARN] 进程未响应 SIGTERM，强制停止..."
    fuser -k -KILL "$port/tcp" 2>/dev/null || true
    sleep 1
  fi
  if fuser "$port/tcp" >/dev/null 2>&1; then
    echo "    [ERROR] 端口 :${port} 仍被占用，无法释放"
    return 1
  fi
  echo "==> 端口 :${port} 已释放"
}

if [ "$ACTION" = "stop" ]; then
  stop_api
  exit 0
fi
if [ "$ACTION" = "restart" ]; then
  stop_api
  sleep 1
fi

# 确保依赖服务在运行（复用与 init_env.sh 相同的启动逻辑，兼容无 systemd 的 Notebook 容器）
echo "==> 检查 MySQL / Redis"
# shellcheck disable=SC1091
source "$PROJECT_ROOT/deploy/common/lib_services.sh"
start_mysql || true
if ! wait_mysql 30; then
  echo "    [WARN] MySQL 未就绪，请检查：tail -30 /var/log/mysql/error.log"
  echo "           手动拉起：sudo mysqld_safe --user=mysql &"
fi
start_redis || true
if redis_alive; then
  echo "    Redis 已就绪"
else
  echo "    [WARN] Redis 未就绪（任务将降级为 API 进程内执行；--worker 模式需要 Redis）"
fi

# 可选：Celery Worker（需要 Redis；任务通过 broker 派发，API 重启不中断）
if [ "$WITH_WORKER" -eq 1 ]; then
  echo "==> 启动 Celery Worker"
  (cd backend && nohup python3 -m celery -A app.tasks.worker:celery_app worker --loglevel=info \
      > "$PROJECT_ROOT/backend/celery.log" 2>&1 &)
  echo "    Worker 日志：backend/celery.log"
fi

# 启动前先释放目标端口，避免旧进程残留导致 address already in use
free_port "$PORT" || exit 1

echo "==> 启动后端 API（:${PORT}，前端由 FastAPI 托管）"
cd backend
if [ "$BACKGROUND" -eq 1 ]; then
  nohup python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" \
      > "$PROJECT_ROOT/backend/api.log" 2>&1 &
  echo "$!" > "$PROJECT_ROOT/backend/api.pid"
  sleep 2
  if kill -0 "$(cat "$PROJECT_ROOT/backend/api.pid")" 2>/dev/null; then
    echo "    API 已在后台启动：PID $(cat "$PROJECT_ROOT/backend/api.pid")"
    echo "    日志：backend/api.log；停止：bash deploy/notebook/start.sh --stop"
  else
    echo "    [ERROR] API 启动失败，请查看 backend/api.log"
    exit 1
  fi
else
  exec python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
fi
