#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · Ubuntu 24.04 systemd 服务安装脚本（推荐服务器长期运行）
#
# 安装内容：
#   1. llm-train-api.service    —— FastAPI 后端（开机自启 + 崩溃自动拉起）
#   2. llm-train-worker.service —— Celery Worker（任务独立进程；需 Redis）
#   3. （可选 --with-nginx）Nginx 反代 80 → 8000（含 WebSocket）
#
# 用法：
#   bash deploy/ubuntu/install_systemd.sh              # 安装 api + worker 两个服务
#   bash deploy/ubuntu/install_systemd.sh --api-only   # 仅安装 API 服务
#   bash deploy/ubuntu/install_systemd.sh --with-nginx # 同时安装 Nginx 反代
#   bash deploy/ubuntu/install_systemd.sh --remove     # 卸载并停止服务
#
# 前置条件：已执行 deploy/ubuntu/init_env.sh（backend/.venv 存在）
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "[ERROR] 需要 root/sudo 安装 systemd 服务"
    exit 1
  fi
fi

WITH_NGINX=0
API_ONLY=0
ACTION="install"
for arg in "$@"; do
  case "$arg" in
    --with-nginx) WITH_NGINX=1 ;;
    --api-only)   API_ONLY=1 ;;
    --remove)     ACTION="remove" ;;
  esac
done

# 运行服务的系统用户：sudo 调用取 $SUDO_USER，否则取当前登录用户（非 root），最后回退 root
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
  RUN_USER="$SUDO_USER"
elif [ "$(id -u)" -ne 0 ]; then
  RUN_USER="$(id -un)"
else
  RUN_USER="root"
fi
echo "==> systemd 服务运行用户: $RUN_USER"

VENV_PY="$PROJECT_ROOT/backend/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  echo "[ERROR] 未找到 $VENV_PY，请先执行 bash deploy/ubuntu/init_env.sh"
  exit 1
fi

if [ "$ACTION" = "remove" ]; then
  echo "==> 卸载服务"
  $SUDO systemctl disable --now llm-train-api.service 2>/dev/null || true
  $SUDO systemctl disable --now llm-train-worker.service 2>/dev/null || true
  $SUDO rm -f /etc/systemd/system/llm-train-api.service /etc/systemd/system/llm-train-worker.service
  $SUDO systemctl daemon-reload
  echo "    已卸载（Nginx 配置未删除，如需删除：sudo rm -f /etc/nginx/sites-enabled/llm-train）"
  exit 0
fi

echo "==> 渲染 systemd 单元文件并安装"
SED_EXPR="s|__PROJECT_DIR__|$PROJECT_ROOT|g; s|__RUN_USER__|$RUN_USER|g"
# 用 tee 落盘：sed 与写 /etc/systemd/system 均在 root 权限下完成（当前用户可能非 root）
$SUDO sed -e "$SED_EXPR" deploy/ubuntu/systemd/llm-train-api.service \
    | $SUDO tee /etc/systemd/system/llm-train-api.service > /dev/null
$SUDO systemctl daemon-reload
$SUDO systemctl enable llm-train-api.service
$SUDO systemctl restart llm-train-api.service
echo "    llm-train-api.service 已启动：sudo systemctl status llm-train-api"

if [ "$API_ONLY" -eq 0 ]; then
  $SUDO sed -e "$SED_EXPR" deploy/ubuntu/systemd/llm-train-worker.service \
      | $SUDO tee /etc/systemd/system/llm-train-worker.service > /dev/null
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable llm-train-worker.service
  $SUDO systemctl restart llm-train-worker.service
  echo "    llm-train-worker.service 已启动：sudo systemctl status llm-train-worker"
else
  echo "    （--api-only，跳过 worker 服务）"
fi

if [ "$WITH_NGINX" -eq 1 ]; then
  echo "==> 安装 Nginx 反代（80 → 8000）"
  if ! command -v nginx >/dev/null 2>&1; then
    $SUDO apt-get update -y
    $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y nginx
  fi
  $SUDO cp deploy/ubuntu/nginx.conf /etc/nginx/sites-available/llm-train
  # 停用默认站点（占 80 端口），启用平台站点
  $SUDO rm -f /etc/nginx/sites-enabled/default
  $SUDO ln -sf /etc/nginx/sites-available/llm-train /etc/nginx/sites-enabled/llm-train
  if $SUDO nginx -t; then
    $SUDO systemctl reload nginx
    echo "    Nginx 已就绪：http://<服务器IP>/  ->  http://127.0.0.1:8000"
  else
    echo "    [ERROR] nginx -t 校验失败，请检查 /etc/nginx/nginx.conf"
    exit 1
  fi
fi

echo ""
echo "============================================================"
echo "systemd 服务安装完成："
echo "  API     : sudo systemctl status llm-train-api"
echo "  Worker  : sudo systemctl status llm-train-worker"
echo "  日志    : sudo journalctl -u llm-train-api -f"
echo "  Nginx   : ${WITH_NGINX:-0}（80 端口）"
if [ "$WITH_NGINX" -eq 1 ]; then
  echo "访问地址：http://<服务器IP>/"
else
  echo "访问地址：http://<服务器IP>:8000/"
fi
echo "默认账号：admin / admin123（启动后请尽快修改）"
echo "============================================================"
