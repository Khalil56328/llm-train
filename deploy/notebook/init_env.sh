#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · ModelScope Notebook 一键初始化脚本
# 用法：bash deploy/notebook/init_env.sh
# 说明：在 GPU Notebook 终端执行一次即可完成环境初始化
#   - 环境自检（GPU / Python / Node / 磁盘空间 / modelscope 库）
#   - 安装并启动 MySQL / Redis（免 Docker）
#   - 安装后端 Python 依赖
#   - 安装 MS-Swift + vLLM（真实训练/推理引擎，安装最新版并校验 torch 防降级）
#   - 构建前端 dist
#   - 生成 backend/.env + 训练工作目录 backend/workspace
#
# 已验证镜像：ubuntu22.04-cuda12.8.1-py312-torch2.10.0-1.39.0
#   （Ubuntu 22.04 / CUDA 12.8.1 / Python 3.12 / torch 2.10.0 / 预装 modelscope；
#     无 Docker，默认无 Node.js）
#
# 环境变量（可选）：
#   PIP_INDEX_URL     pip 镜像源（默认走系统配置；国内网络可设
#                     https://pypi.tuna.tsinghua.edu.cn/simple 加速）
#   NPM_REGISTRY      npm 镜像源（默认 https://registry.npmmirror.com）
#   TORCH_WHEEL_INDEX torch cu128 wheel 镜像源（默认 https://mirrors.aliyun.com/pytorch-wheels/cu128；
#                     备用 https://mirrors.tuna.tsinghua.edu.cn/pytorch-wheels/cu128 或
#                     https://mirrors.cloud.tencent.com/pytorch-wheels/cu128；
#                     仅在引擎安装把 torch 换成非 cu128 构建时用于恢复）
# ============================================================
set -euo pipefail

# ---------- 项目根目录定位（脚本在 deploy/notebook/ 下） ----------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# 检测 sudo（魔搭 Notebook 默认 admin 用户具备 sudo）
if command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
fi

# 可选环境变量默认值
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
# 安装大件（MS-Swift / vLLM / torch）所需的最低磁盘余量（GB）
MIN_DISK_GB=12

# 提前加载依赖服务辅助函数（仅定义函数，无副作用）：
# mysql_port_alive / redis_port_alive 用于识别 docker/外部提供的 MySQL、Redis
# shellcheck disable=SC1091
source "$PROJECT_ROOT/deploy/common/lib_services.sh"

# ---------- Node.js 安装（NodeSource 20；Vite 5 要求 Node >= 18） ----------
# NodeSource 旧版 setup_20.x 脚本已弃用，优先用新版 gpg keyring + apt 源方式，
# 失败时回退旧脚本（旧脚本仍可用但有弃用告警）。
install_node() {
  echo "    安装 Node.js 20（NodeSource）..."
  if ! command -v curl >/dev/null 2>&1; then
    $SUDO apt-get install -y curl
  fi
  if ! command -v gpg >/dev/null 2>&1; then
    $SUDO apt-get install -y gnupg
  fi
  $SUDO install -d -m 0755 /etc/apt/keyrings 2>/dev/null || true
  if curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o /tmp/nodesource.gpg.key 2>/dev/null; then
    $SUDO gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg /tmp/nodesource.gpg.key 2>/dev/null || true
  fi
  if [ -f /etc/apt/keyrings/nodesource.gpg ]; then
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
      | $SUDO tee /etc/apt/sources.list.d/nodesource.list >/dev/null
    $SUDO apt-get update -y
    $SUDO apt-get install -y nodejs
  else
    echo "    NodeSource 新版源配置失败，回退旧 setup_20.x 脚本..."
    if [ -n "$SUDO" ]; then
      curl -fsSL https://deb.nodesource.com/setup_20.x | $SUDO -E bash -
    else
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash
    fi
    $SUDO apt-get install -y nodejs
  fi
  command -v node >/dev/null 2>&1 || echo "    [ERROR] Node 安装失败，请手动安装 Node 20+ 后重跑脚本"
}

echo "==> [1/8] 环境自检（GPU / Python / Node / 磁盘 / modelscope）"
GPU_LINE="$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1 || true)"
if [ -n "$GPU_LINE" ]; then
  echo "    GPU: $GPU_LINE"
else
  echo "    [WARN] 未检测到 NVIDIA GPU（无 nvidia-smi 或无可用 GPU）："
  echo "          真实训练/推理不可用，TRAIN_EXECUTION_MODE=auto 将自动走 mock 流程"
fi
PY_MAJOR="$(python3 -c 'import sys;print(sys.version_info.major)' 2>/dev/null || echo 0)"
PY_MINOR="$(python3 -c 'import sys;print(sys.version_info.minor)' 2>/dev/null || echo 0)"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  echo "    [WARN] Python 版本过低（$(python3 --version 2>/dev/null || echo 未知)），后端要求 3.10+"
else
  echo "    Python: $(python3 --version 2>/dev/null)"
fi
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -v | sed 's/^v//' | cut -d. -f1)"
  echo "    Node: $(node -v)"
  if [ "${NODE_MAJOR:-0}" -lt 18 ]; then
    echo "    [WARN] Node < 18，Vite 5 无法构建，自动升级到 Node 20"
    install_node
  fi
else
  echo "    未检测到 Node.js，自动安装 Node 20"
  install_node
fi
# 磁盘空间预检：MS-Swift + vLLM + torch 及相关依赖约需 8~12GB，空间不足直接给出提示
DISK_GB="$(df -BG --output=avail "$PROJECT_ROOT" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)"
if [ -n "$DISK_GB" ] && [ "$DISK_GB" -lt "$MIN_DISK_GB" ]; then
  echo "    [WARN] 磁盘剩余空间 ${DISK_GB}GB < ${MIN_DISK_GB}GB，安装 MS-Swift/vLLM 可能失败。"
  echo "          请先清理（du -sh * 定位大目录；Notebook 实例释放后磁盘不保留）或换更大磁盘实例"
fi
# modelscope 库校验（该镜像已预装 ModelScope Library；个别镜像变体缺失时补装，
# 否则 modelscope 数据集中转 / 模型下载不可用）
if python3 -c "import modelscope" 2>/dev/null; then
  echo "    modelscope: $(python3 -c 'import modelscope;print(getattr(modelscope,\"__version__\",\"?\"))' 2>/dev/null || echo '?')"
else
  echo "    [WARN] 未检测到 modelscope 库，自动安装（模型/数据集下载与中转依赖它）..."
  python3 -m pip install -q modelscope
fi

echo "==> [2/8] 安装系统依赖（MySQL / Redis）"
$SUDO apt-get update -y
# 依赖服务自动识别：3306/6379 已有监听（外部已部署 / 残留实例）
# 时跳过本机 mysql-server/redis-server 安装
NEED_MYSQL=1
NEED_REDIS=1
if mysql_port_alive; then
  NEED_MYSQL=0
  echo "    [INFO] 127.0.0.1:3306 已有 MySQL（外部提供），跳过本机安装"
fi
if redis_port_alive; then
  NEED_REDIS=0
  echo "    [INFO] 127.0.0.1:6379 已有 Redis（外部提供），跳过本机安装"
fi
PKG_LIST="unzip"
[ "$NEED_MYSQL" -eq 1 ] && PKG_LIST="$PKG_LIST mysql-server"
[ "$NEED_REDIS" -eq 1 ] && PKG_LIST="$PKG_LIST redis-server"
# shellcheck disable=SC2086
# 注意：不要写成 `$SUDO DEBIAN_FRONTEND=... apt-get`——root 执行时 SUDO 为空，
# bash 不会把展开后的 DEBIAN_FRONTEND= 重新识别为赋值前缀，会报 "command not found"。
# 用 env 传环境变量，root / sudo 两种执行方式均正常。
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y $PKG_LIST

echo "==> [3/8] 启动 MySQL / Redis 并初始化数据库"
# 加载服务启动辅助函数（兼容本机 apt / 外部已运行服务 / 无 systemd 容器三种环境）
# start_mysql/start_redis 会先探测端口：已有服务在监听时直接视为就绪，不拉起本机实例

# --- MySQL：启动 + 等待就绪（最多 60s），失败则给出诊断并退出 ---
start_mysql || true
if ! wait_mysql 60; then
  echo "    [ERROR] MySQL 60 秒内未就绪，诊断日志："
  $SUDO tail -n 30 /var/log/mysql/error.log 2>/dev/null || echo "    （无 /var/log/mysql/error.log）"
  $SUDO tail -n 30 /tmp/mysqld_safe.log 2>/dev/null || echo "    （无 /tmp/mysqld_safe.log）"
  echo "    [ERROR] 排查建议："
  echo "            1) sudo mkdir -p /var/run/mysqld && sudo chown mysql:mysql /var/run/mysqld"
  echo "            2) sudo mysqld_safe --user=mysql &   # 手动拉起后重跑本脚本"
  echo "            3) 数据目录损坏时：sudo rm -rf /var/lib/mysql && sudo mysqld --initialize-insecure"
  exit 1
fi
echo "    MySQL 已就绪"

# --- Redis：尽力启动（失败不阻断；任务会降级为 API 进程内执行） ---
start_redis || true
if redis_alive; then
  echo "    Redis 已就绪"
else
  echo "    [WARN] Redis 未就绪（任务将降级为 API 进程内执行；--worker 模式需要 Redis）"
fi

# 建库建用户（幂等；本机 socket / 外部 TCP root 均自动兼容）
mysql_init_db deploy/mysql/init.sql || true
echo "    数据库 llm_train 初始化完成"

echo "==> [4/8] 安装后端依赖"
python3 -m pip install --upgrade pip
# 国内网络可选：PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple bash deploy/notebook/init_env.sh
if [ -n "$PIP_INDEX_URL" ]; then
  python3 -m pip install --no-cache-dir -r backend/requirements.txt --index-url "$PIP_INDEX_URL"
else
  python3 -m pip install --no-cache-dir -r backend/requirements.txt
fi

echo "==> [5/8] 安装训练/推理引擎（MS-Swift + vLLM）"
echo "    镜像自带 torch 2.10.0（CUDA 12.8.1 / py312）；此处仅安装上层引擎"
# vLLM 对 torch 精确锁定（==），版本不匹配会导致 import 失败：
#   vllm 0.17~0.19 → torch==2.10.0  |  vllm 0.20+ → torch==2.11.0
# 镜像自带 torch 2.10.0+cu128，须锁定 vllm<=0.19.x。
VLLM_VERSION="${VLLM_VERSION:-0.19.0}"
TORCH_BEFORE="$(python3 -c 'import torch;print(torch.__version__)' 2>/dev/null || echo '?')"
echo "    安装前 torch: ${TORCH_BEFORE}"
# 不再固定 ms-swift==2.5.1：2.5.1（2024-11）与 torch 2.10.0 / py312 时代错位，
# 其依赖（transformers/trl 等）解析到最新版后运行期不兼容；直接装最新版（3.x/4.x 官方支持 py312）。
if [ -n "$PIP_INDEX_URL" ]; then
  python3 -m pip install --no-cache-dir ms-swift "vllm==${VLLM_VERSION}" \
      --extra-index-url "https://download.pytorch.org/whl/cu128" \
      --index-url "$PIP_INDEX_URL" || {
    echo "    [WARN] 引擎安装未完全成功；TRAIN_EXECUTION_MODE=auto 会自动降级 mock，可先跑通业务流"
  }
else
  python3 -m pip install --no-cache-dir ms-swift "vllm==${VLLM_VERSION}" \
      --extra-index-url "https://download.pytorch.org/whl/cu128" || {
    echo "    [WARN] 引擎安装未完全成功；TRAIN_EXECUTION_MODE=auto 会自动降级 mock，可先跑通业务流"
  }
fi
# torch 防降级校验：vLLM 精确锁定 torch 版本（如 vllm 0.19.0 锁 torch==2.10.0），
# 正常情况下安装后 torch 版本应不变。若因依赖冲突被换成非 cu128 构建才需恢复。
TORCH_AFTER="$(python3 -c 'import torch;print(torch.__version__)' 2>/dev/null || echo '?')"
echo "    安装后 torch: ${TORCH_AFTER}"
if [ "$TORCH_BEFORE" != "?" ] && [ "$TORCH_AFTER" != "?" ] && [ "$TORCH_BEFORE" != "$TORCH_AFTER" ]; then
  case "$TORCH_AFTER" in
    *+cu128*)
      echo "    [INFO] 引擎依赖解析将 torch 从 ${TORCH_BEFORE} 调整为 ${TORCH_AFTER}。"
      echo "           ${TORCH_AFTER} 为 cu128（CUDA 12.8）构建，与镜像 CUDA 12.8.1 兼容，保留该版本"
      echo "           （vLLM 等引擎按自身依赖锁定 torch 版本，强改会破坏引擎）。"
      ;;
    *)
      echo "    [ERROR] torch 被改为 ${TORCH_AFTER}（非 cu128 构建），尝试从 cu128 源恢复 ${TORCH_BEFORE}..."
      TORCH_WHEEL_INDEX="${TORCH_WHEEL_INDEX:-https://mirrors.aliyun.com/pytorch-wheels/cu128}"
      if python3 -m pip install --no-cache-dir "torch==${TORCH_BEFORE}" --index-url "$TORCH_WHEEL_INDEX" \
          --timeout 120 --retries 10; then
        TORCH_RESTORED="$(python3 -c 'import torch;print(torch.__version__)' 2>/dev/null || echo '?')"
        if [ "$TORCH_RESTORED" = "$TORCH_BEFORE" ]; then
          echo "    torch 已恢复为 ${TORCH_BEFORE}"
        else
          echo "    [ERROR] torch 恢复失败（当前 ${TORCH_RESTORED}）。"
          echo "            请重置镜像后重跑本脚本，或在安装引擎时显式锁定 torch 版本。"
          exit 1
        fi
      else
        echo "    [ERROR] torch 恢复失败（网络问题？）。可手动执行："
        echo "            python3 -m pip install \"torch==${TORCH_BEFORE}\" --index-url \"$TORCH_WHEEL_INDEX\" --timeout 120 --retries 10"
        echo "            或换用其他镜像：https://mirrors.tuna.tsinghua.edu.cn/pytorch-wheels/cu128"
        echo "            或 https://mirrors.cloud.tencent.com/pytorch-wheels/cu128"
        exit 1
      fi
      ;;
  esac
fi
# 清理引擎依赖解析报告的部分依赖冲突：
#   - ms-agent 1.6.0 需要 edge-tts / faiss-cpu / moviepy（未随引擎解析装上）
#   - ms-opencompass 0.1.6 要求 numpy<2.0.0（解析时装成了 2.x）
# 失败不影响训练/推理主流程，仅告警（用到 ms-agent / ms-opencompass 相关功能时再手动补装）。
echo "    清理引擎依赖冲突（numpy<2 / edge-tts / faiss-cpu / moviepy）..."
if [ -n "$PIP_INDEX_URL" ]; then
  python3 -m pip install --no-cache-dir "numpy>=1.23.4,<2.0.0" edge-tts faiss-cpu moviepy --index-url "$PIP_INDEX_URL" \
    || echo "    [WARN] 依赖冲突清理未完全成功（不影响训练/推理主流程）"
else
  python3 -m pip install --no-cache-dir "numpy>=1.23.4,<2.0.0" edge-tts faiss-cpu moviepy \
    || echo "    [WARN] 依赖冲突清理未完全成功（不影响训练/推理主流程）"
fi
# numpy 降级后快速校验 torch 仍可导入（torch 2.8 支持 numpy 1.26）
if ! python3 -c "import torch" 2>/dev/null; then
  echo "    [ERROR] 清理依赖后 torch 无法导入，请检查 numpy/torch 版本兼容性"
  exit 1
fi

# 打印引擎版本，便于确认与 ms-swift 4.x / 新版 vLLM 的兼容性
echo "    ms-swift: $(python3 -c 'import swift;print(getattr(swift, \"__version__\", \"?\"))' 2>/dev/null || echo '?')"
echo "    vllm:     $(python3 -m vllm --version 2>/dev/null || echo '?')"
# vLLM 安装校验：import 失败（如无 GPU 环境 / 依赖冲突）时提示降级 mock，
# 不阻塞后续步骤（auto 模式由执行器按 GPU 探测自动降级）
if python3 -c "import vllm" 2>/dev/null; then
  echo "    vllm import 校验通过"
else
  echo "    [WARN] vllm import 失败（无 GPU / 依赖冲突）；推理将不可用，训练不受影响"
fi
# 清理残缺的 apex 包：transformers 用 find_spec('apex') 判定 apex 可用，
# 若装到的是无 amp 模块的同名包（PyPI 旧包/半成品安装），swift 导入时
# 会抛 "cannot import name 'amp' from 'apex'" 直接崩溃；训练本身不需要 apex。
if python3 -c "import apex" 2>/dev/null; then
  if ! python3 -c "import apex.amp" 2>/dev/null; then
    echo "    [WARN] 检测到残缺的 apex 包（import apex.amp 失败），卸载以避免 transformers 导入崩溃"
    python3 -m pip uninstall -y apex || true
  fi
fi

echo "==> [6/8] 构建前端"
cd web-ui
npm install --registry="$NPM_REGISTRY"
npm run build
cd "$PROJECT_ROOT"

echo "==> [7/8] 生成 backend/.env（如不存在）+ 训练工作目录"
if [ ! -f backend/.env ]; then
  cp deploy/notebook/.env.notebook backend/.env
  echo "    已生成 backend/.env，请按需修改 JWT_SECRET_KEY / TRAIN_WORKSPACE"
else
  echo "    backend/.env 已存在，跳过"
fi
mkdir -p backend/workspace
mkdir -p backend/workspace/models
mkdir -p backend/workspace/datasets
echo "    已创建训练工作目录 backend/workspace（含 models/ datasets/，供模型/数据集落盘）"
echo "    提示：真实训练前用 deploy/common/download_models.sh 下载模型到 workspace/models，"
echo "          并在平台把模型/数据集的 storage_path 指向真实路径（详见 README 常见问题）"

# ---------- 下载默认模型（SEED_MODEL_ID 非空时自动下载并录入模型库） ----------
SEED_MODEL_ID="$(grep -E '^SEED_MODEL_ID=' backend/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
if [ -n "$SEED_MODEL_ID" ]; then
  echo "==> 下载默认模型: ${SEED_MODEL_ID}（约 0.5~1GB，视网速可能较久；失败不影响初始化）"
  if bash deploy/common/download_models.sh --model "$SEED_MODEL_ID"; then
    echo "    默认模型已下载并录入模型库（我的模型库 / 模型库广场可见，文件指向真实路径）"
  else
    echo "    [WARN] 默认模型下载失败（网络问题？），可稍后手动执行："
    echo "           bash deploy/common/download_models.sh --model $SEED_MODEL_ID"
    echo "           （成功后会同时自动录入模型库）"
  fi
else
  echo "    未配置 SEED_MODEL_ID，跳过默认模型下载（如需自动安装，在 backend/.env 配置后重跑本脚本）"
fi

# ---------- 生成演示数据集（SFT / 偏好 / 预训练文本，供训练向导开箱可选） ----------
echo "==> 生成演示数据集（SFT / 偏好 / 预训练文本，供训练向导开箱可选）..."
if python3 deploy/common/seed_demo_data.py --root backend/workspace --samples 200; then
  echo "    演示数据集已生成（backend/workspace/datasets/），后端启动时自动录入数据集管理"
else
  echo "    [WARN] 演示数据集生成失败，可稍后手动执行："
  echo "           python3 deploy/common/seed_demo_data.py --root backend/workspace"
fi

echo "==> [8/8] 验证后端模块导入"
cd backend
python3 test_import.py

echo ""
echo "============================================================"
echo "初始化完成！启动服务：bash deploy/notebook/start.sh [--worker] [--port=8000]"
echo "访问地址：http://127.0.0.1:8000（可在 Notebook 控制台做端口映射对外访问）"
echo "默认账号：admin / admin123（启动后请尽快修改）"
echo "------------------------------------------------------------"
echo "后续常用操作："
echo "  - 下载真实模型:  bash deploy/common/download_models.sh --model Qwen/Qwen2.5-0.5B-Instruct"
echo "  - 重新生成演示数据集: python3 deploy/common/seed_demo_data.py --root backend/workspace"
echo "  - 数据备份:      bash deploy/common/backup.sh   （mysqldump + 模型/存储打包）"
echo "  - 实例重建恢复:  重新 unzip + bash deploy/notebook/init_env.sh"
echo "============================================================"
