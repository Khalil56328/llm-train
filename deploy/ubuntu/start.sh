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

# 把 venv/bin 加入 PATH：引擎（MS-Swift 的 swift CLI、vLLM 等）以 console_scripts
# 形式安装在该目录，executor 通过 shutil.which("swift") 探测并用 PATH 定位子进程命令。
# 若此处不加入 PATH，exec_mode() 在 auto 模式下会因找不到 swift 而降级为 mock，
# 真实训练/推理也会因 subprocess 找不到命令而失败。
VENV_BIN="$(dirname "$PY")"
if [ -d "$VENV_BIN" ]; then
  case ":$PATH:" in
    *":$VENV_BIN:"*) : ;;
    *) export PATH="$VENV_BIN:$PATH" ;;
  esac
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

stop_pidfile() {
  # 通用停止：pid 文件存在且进程存活则优雅终止（最多 10s 后强杀），再清理 pid 文件
  local pidfile="$1" label="$2"
  if [ -f "$pidfile" ]; then
    local pid
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "==> 停止 ${label}（PID $pid）"
      kill "$pid" 2>/dev/null || true
      for _ in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      kill -9 "$pid" 2>/dev/null || true
    else
      echo "==> ${label} 未在运行（PID 文件过期）"
    fi
    rm -f "$pidfile"
  else
    echo "==> 未找到 ${pidfile}，跳过停止 ${label}"
  fi
}

stop_api() {
  stop_pidfile "$PROJECT_ROOT/backend/api.pid" "后台 API"
}

stop_worker() {
  # 1) 按 pid 文件停止（后台启动 worker 时记录）
  stop_pidfile "$PROJECT_ROOT/backend/celery.pid" "Celery Worker"

  # 2) 兜底：清理任何残留的 celery worker 进程（celery 是 prefork 多进程，
  #    主进程 pid 文件记录的只是主进程，子进程需一并清掉；pid 文件缺失时
  #    旧 worker 会残留并继续消费任务——它们加载的是旧代码，必须彻底清掉）。
  #    按 celery 工作进程名匹配：-A app.tasks.worker 或 python -m celery
  if command -v pkill >/dev/null 2>&1; then
    if pkill -f "app\.tasks\.worker" >/dev/null 2>&1; then
      echo "==> 已清理残留的 Celery Worker 进程（按模块名匹配）"
    fi
  fi
}

# 释放指定端口：按端口检测并停止占用进程。
# 用于兜底 pid 文件不可靠的场景（如前台启动未写 pid、PID 文件丢失、uvicorn --reload 子进程残留），
# 避免启动时报 [Errno 98] address already in use。
free_port() {
  local port="$1"
  if ! command -v fuser >/dev/null 2>&1; then
    echo "    [WARN] 未找到 fuser，跳过端口清理（请先执行：apt-get install -y psmisc 或 lsof）"
    return 0
  fi
  if ! fuser "$port/tcp" >/dev/null 2>&1; then
    return 0  # 端口空闲
  fi
  echo "==> 端口 :${port} 被占用，正在停止占用进程..."
  # fuser -k 用 SIGTERM 优雅停止监听该端口的进程（-TERM）
  fuser -k -TERM "$port/tcp" 2>/dev/null || true
  # 等待端口释放（最多 10s），未释放再强制 SIGKILL
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
  stop_worker
  exit 0
fi
if [ "$ACTION" = "restart" ]; then
  stop_api
  stop_worker
  sleep 1
fi

# 确保依赖服务在运行（复用 Notebook 的辅助函数，兼容 systemd 服务器）
echo "==> 检查 MySQL / Redis"
# shellcheck disable=SC1091
source "$PROJECT_ROOT/deploy/common/lib_services.sh"
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
  # 启动前先清掉旧 worker，避免残留进程（旧代码）继续消费任务导致新代码不生效
  stop_worker
  echo "==> 启动 Celery Worker"
  (cd backend && nohup "$PY" -m celery -A app.tasks.worker:celery_app worker --loglevel=info \
      > "$PROJECT_ROOT/backend/celery.log" 2>&1 & echo $! > "$PROJECT_ROOT/backend/celery.pid")
  echo "    Worker 日志：backend/celery.log"
fi

# 启动前先释放目标端口，避免旧进程残留导致 address already in use
free_port "$PORT" || exit 1

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
