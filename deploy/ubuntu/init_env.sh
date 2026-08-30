#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · Ubuntu 24.04 全新服务器一键初始化脚本
# 用法：
#   bash deploy/ubuntu/init_env.sh                      # 常规初始化
#   sudo bash deploy/ubuntu/init_env.sh                 # 当前用户无 sudo 时用 root 执行
#   bash deploy/ubuntu/init_env.sh --install-driver     # 同时自动安装 NVIDIA 驱动（需重启后重跑）
#   bash deploy/ubuntu/init_env.sh --with-quant         # 额外安装全部量化框架（GPTQ/AWQ/GGUF，编译较重；
#                                                       #   bnb/bitsandbytes 默认随 GPU 环境安装）
#
# 说明（与 ModelScope Notebook 环境的差异适配）：
#   - Ubuntu 24.04 默认 Python 3.12，且 PEP 668 禁止向系统 Python pip 安装
#     → 后端与引擎统一安装到独立 venv：backend/.venv
#   - 有 NVIDIA GPU（nvidia-smi 可用）：
#       安装 torch cu128 + ms-swift + vLLM，TRAIN_EXECUTION_MODE=auto 走真实训练/推理
#   - 无 GPU / 未装驱动：
#       安装 torch CPU + ms-swift，并把 TRAIN_EXECUTION_MODE 改为 mock（业务流可跑通）
#   - MySQL / Redis：默认本机 apt + systemd 安装；若 3306/6379 端口已有服务
#     （外部已部署 / 残留实例），自动识别并跳过本机安装与初始化
#   - Node.js 通过 NodeSource 安装 Node 20（apt 自带 nodejs 为 18 且无 npm，不满足构建要求）
#
# 环境变量（可选）：
#   PIP_INDEX_URL     pip 镜像源（国内网络可设 https://pypi.tuna.tsinghua.edu.cn/simple）
#   NPM_REGISTRY      npm 镜像源（默认 https://registry.npmmirror.com）
#   CUDA_VERSION      torch 轮子的 CUDA 版本（默认 cu128；驱动 <570 时可改 cu124）
#   TORCH_VERSION     torch 版本（默认 2.10.0；改版本时须同步调整 VLLM_VERSION）
#   VLLM_VERSION      vllm 版本（默认 0.19.0；须与 TORCH_VERSION 严格对应：
#                       vllm 0.17~0.19→torch 2.10 | vllm 0.20+→torch 2.11 | vllm 0.13~0.16→torch 2.9.x）
# ============================================================
set -euo pipefail

# ---------- 项目根目录定位（脚本在 deploy/ubuntu/ 下） ----------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# 检测 sudo（Ubuntu 24.04 默认管理员可 sudo；root 直接执行时为空）
if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
  else
    echo "[ERROR] 当前用户无 sudo，请用 root 执行或先为当前用户配置 sudo"
    exit 1
  fi
fi

INSTALL_DRIVER=0
WITH_QUANT=0
for arg in "$@"; do
  case "$arg" in
    --install-driver) INSTALL_DRIVER=1 ;;
    --with-quant) WITH_QUANT=1 ;;
  esac
done

# 提前加载依赖服务辅助函数（仅定义函数，无副作用）：
# mysql_port_alive / redis_port_alive 用于识别 docker/外部提供的 MySQL、Redis
# shellcheck disable=SC1091
source "$PROJECT_ROOT/deploy/common/lib_services.sh"

# 可选环境变量默认值
PIP_INDEX_URL="${PIP_INDEX_URL:-}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
# 默认值对齐：CUDA 12.8（cu128）+ torch 2.10.0 + vllm 0.19.0。
# vLLM 对 torch 采取精确锁定（==），版本不匹配则 import 或运行失败：
#   vllm 0.17~0.19 → torch==2.10.0  |  vllm 0.20+ → torch==2.11.0  |  vllm 0.13~0.16 → torch==2.9.x
# 当前默认 cu128+torch2.10.0+vllm0.19.0 是 CUDA 12.8 驱动下的稳定组合；
# 若需更新引擎，设置 TORCH_VERSION=2.11.0 VLLM_VERSION=0.23.0（cu128 同样有 torch 2.11.0 构建）。
CUDA_VERSION="${CUDA_VERSION:-cu128}"
TORCH_VERSION="${TORCH_VERSION:-2.10.0}"
VLLM_VERSION="${VLLM_VERSION:-0.19.0}"
# torch/torchvision/torchaudio 版本配套（torchvision 主版本比 torch 低，torchaudio 与 torch 同号）。
# 可分别用 TORCHVISION_VERSION / TORCHAUDIO_VERSION 覆盖；默认按 TORCH_VERSION 推导，避免
# 重跑脚本时 torchvision/torchaudio 未锁版本被 pip 拉到新版，连带把 torch 升级成不匹配的构建。
TORCHVISION_VERSION="${TORCHVISION_VERSION:-}"
TORCHAUDIO_VERSION="${TORCHAUDIO_VERSION:-}"
if [ -z "$TORCHVISION_VERSION" ] || [ -z "$TORCHAUDIO_VERSION" ]; then
  case "$TORCH_VERSION" in
    2.11*) TV=0.26.0; TA=2.11.0 ;;
    2.10*) TV=0.25.0; TA=2.10.0 ;;
    2.9*)  TV=0.24.0; TA=2.9.0 ;;
    2.8*)  TV=0.23.0; TA=2.8.0 ;;
    2.7*)  TV=0.22.0; TA=2.7.0 ;;
    2.6*)  TV=0.21.0; TA=2.6.0 ;;
    2.5*)  TV=0.20.0; TA=2.5.0 ;;
    *)     echo "[WARN] 无法识别 TORCH_VERSION=$TORCH_VERSION 对应的 torchvision/torchaudio 版本，"
           echo "       请显式设置 TORCHVISION_VERSION / TORCHAUDIO_VERSION，否则可能拉取不匹配版本。"
           TV=""; TA="" ;;
  esac
  [ -z "$TORCHVISION_VERSION" ] && TORCHVISION_VERSION="$TV"
  [ -z "$TORCHAUDIO_VERSION" ] && TORCHAUDIO_VERSION="$TA"
fi
MIN_DISK_GB=15
VENV="$PROJECT_ROOT/backend/.venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

# ============================================================
echo "==> [1/9] 环境自检（OS / GPU / Python / 磁盘）"
OS_RELEASE="$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || echo 未知)"
echo "    OS: $OS_RELEASE"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  echo "    GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)"
  HAS_GPU=1
else
  HAS_GPU=0
  echo "    [WARN] 未检测到 NVIDIA GPU（无 nvidia-smi 或驱动未装）"
  echo "           - 真实训练/推理需要 NVIDIA 驱动（建议 >=570 以支持 CUDA 12.8）"
  echo "           - 可继续初始化：将以 mock 模式跑通业务流，装好驱动后重跑脚本升级为真实模式"
fi
PY_VER="$(python3 --version 2>/dev/null || echo 未知)"
echo "    Python: $PY_VER（Ubuntu 24.04 默认 3.12，满足后端 >=3.10 要求）"
DISK_GB="$(df -BG --output=avail "$PROJECT_ROOT" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)"
if [ -n "$DISK_GB" ] && [ "$DISK_GB" -lt "$MIN_DISK_GB" ]; then
  echo "    [WARN] 磁盘剩余 ${DISK_GB}GB < ${MIN_DISK_GB}GB：torch + MS-Swift + vLLM 约需 10~15GB，"
  echo "          建议扩容或清理（du -sh * 定位大目录）后重跑"
fi

if [ "$INSTALL_DRIVER" -eq 1 ] && [ "$HAS_GPU" -eq 0 ]; then
  echo "==> 安装 NVIDIA 驱动（ubuntu-drivers autoinstall）..."
  $SUDO apt-get update -y
  $SUDO apt-get install -y ubuntu-drivers-common
  $SUDO ubuntu-drivers autoinstall || {
    echo "[ERROR] 驱动自动安装失败，请手动安装：sudo ubuntu-drivers autoinstall"
    exit 1
  }
  echo "    驱动安装完成，请【重启机器】后重新执行：bash deploy/ubuntu/init_env.sh"
  exit 0
fi

# ============================================================
echo "==> [2/9] 安装系统依赖（MySQL / Redis / 构建工具 / Node 依赖）"
$SUDO apt-get update -y
# 依赖服务自动识别：3306/6379 已有监听（外部已部署 / 残留实例）
# 时跳过本机 mysql-server/redis-server 安装（整个项目仍全部运行在 GPU 宿主机）
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
PKG_LIST="curl ca-certificates gnupg git unzip build-essential python3-venv python3-pip"
[ "$NEED_MYSQL" -eq 1 ] && PKG_LIST="$PKG_LIST mysql-server"
[ "$NEED_REDIS" -eq 1 ] && PKG_LIST="$PKG_LIST redis-server"
# shellcheck disable=SC2086
# 注意：不要写成 `$SUDO DEBIAN_FRONTEND=... apt-get`——root 执行时 SUDO 为空，
# bash 不会把展开后的 DEBIAN_FRONTEND= 重新识别为赋值前缀，会报 "command not found"。
# 用 env 传环境变量，root / sudo 两种执行方式均正常。
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y $PKG_LIST

# ---------- Node.js 安装（NodeSource 20；Vite 5 要求 Node >= 18，apt 自带 18 无 npm 不可用） ----------
install_node() {
  echo "    安装 Node.js 20（NodeSource）..."
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

# ============================================================
echo "==> [3/9] 启动 MySQL / Redis 并初始化数据库"
# 复用 Notebook 的服务启动辅助函数（兼容本机 apt / 外部已运行服务 / 无 systemd 容器）
# start_mysql/start_redis 会先探测端口：容器已提供时直接视为就绪，不拉起本机实例

start_mysql || true
if ! wait_mysql 60; then
  echo "    [ERROR] MySQL 60 秒内未就绪，诊断日志："
  $SUDO tail -n 30 /var/log/mysql/error.log 2>/dev/null || echo "    （无 /var/log/mysql/error.log）"
  echo "    [ERROR] 排查建议：sudo systemctl status mysql"
  exit 1
fi
echo "    MySQL 已就绪"

start_redis || true
if redis_alive; then
  echo "    Redis 已就绪"
else
  echo "    [WARN] Redis 未就绪（任务将降级为 API 进程内执行；--worker 模式需要 Redis）"
fi

# 建库建用户（幂等；本机 socket / 外部 TCP root 均自动兼容）
mysql_init_db deploy/mysql/init.sql || true
echo "    数据库 llm_train 初始化完成"

# ============================================================
echo "==> [4/9] 创建 Python venv 并安装后端依赖"
if [ ! -x "$PY" ]; then
  python3 -m venv "$VENV"
  echo "    已创建 venv: $VENV"
else
  echo "    venv 已存在，跳过创建"
fi
"$PIP" install --upgrade pip
if [ -n "$PIP_INDEX_URL" ]; then
  "$PIP" install --no-cache-dir -r backend/requirements.txt --index-url "$PIP_INDEX_URL"
else
  "$PIP" install --no-cache-dir -r backend/requirements.txt
fi

# ============================================================
echo "==> [5/9] 安装训练/推理引擎（MS-Swift + vLLM）"
if [ "$HAS_GPU" -eq 1 ]; then
  echo "    检测到 GPU：安装 torch ${TORCH_VERSION}（${CUDA_VERSION}）+ ms-swift + vllm==${VLLM_VERSION}"
  echo "    [提示] cu128（CUDA 12.8）需 NVIDIA 驱动 >= 570；"
  echo "           若驱动更旧，改用 CUDA_VERSION=cu124 TORCH_VERSION=2.9.0 VLLM_VERSION=0.14.0 等"
  TORCH_BEFORE="$("$PY" -c 'import torch;print(torch.__version__)' 2>/dev/null || echo '?')"
  echo "    安装前 torch: ${TORCH_BEFORE}"
  # 已安装且版本/构建符合目标（如 2.10.0+cu128 命中 *2.10.0* 且 *+cu128*）时跳过强制重装，
  # 避免重跑脚本时 torchvision/torchaudio 未锁版本把 torch 再次拉成不匹配构建。
  TORCH_TARGET_FIRST="$(echo "$TORCH_VERSION" | cut -d. -f1-2)"
  TORCH_ALREADY_OK=""
  if [ "$TORCH_BEFORE" != "?" ]; then
    case "$TORCH_BEFORE" in
      ${TORCH_TARGET_FIRST}*+${CUDA_VERSION}*)
        echo "    已安装匹配的 torch（${TORCH_BEFORE}），跳过 torch/torchvision/torchaudio 重装"
        TORCH_ALREADY_OK=1
        ;;
    esac
  fi
  if [ -z "$TORCH_ALREADY_OK" ]; then
    "$PIP" install --no-cache-dir "torch==${TORCH_VERSION}" "torchvision==${TORCHVISION_VERSION}" "torchaudio==${TORCHAUDIO_VERSION}" \
        --index-url "https://download.pytorch.org/whl/${CUDA_VERSION}"
  fi
  if [ -n "$PIP_INDEX_URL" ]; then
    "$PIP" install --no-cache-dir ms-swift "vllm==${VLLM_VERSION}" \
        --extra-index-url "https://download.pytorch.org/whl/${CUDA_VERSION}" \
        --index-url "$PIP_INDEX_URL" || {
      echo "    [WARN] 引擎安装未完全成功；TRAIN_EXECUTION_MODE=auto 会自动降级 mock"
    }
  else
    "$PIP" install --no-cache-dir ms-swift "vllm==${VLLM_VERSION}" \
        --extra-index-url "https://download.pytorch.org/whl/${CUDA_VERSION}" || {
      echo "    [WARN] 引擎安装未完全成功；TRAIN_EXECUTION_MODE=auto 会自动降级 mock"
    }
  fi
  # torch 防降级：vLLM 按自身依赖精确锁定 torch 版本（如 vllm 0.19.0 锁 torch==2.10.0），
  # 正常情况下安装后 torch 版本应不变。若因依赖冲突被换成非目标 CUDA 构建才需恢复。
  TORCH_AFTER="$("$PY" -c 'import torch;print(torch.__version__)' 2>/dev/null || echo '?')"
  echo "    安装后 torch: ${TORCH_AFTER}"
  if [ "$TORCH_BEFORE" != "?" ] && [ "$TORCH_AFTER" != "?" ] && [ "$TORCH_BEFORE" != "$TORCH_AFTER" ]; then
    case "$TORCH_AFTER" in
      *+${CUDA_VERSION}*)
        echo "    [INFO] 引擎依赖解析将 torch 从 ${TORCH_BEFORE} 调整为 ${TORCH_AFTER}。"
        echo "           ${TORCH_AFTER} 为 ${CUDA_VERSION}（CUDA ${CUDA_VERSION}）构建，兼容当前驱动，保留该版本"
        echo "           （vLLM 等引擎按自身依赖锁定 torch 版本，强改会破坏引擎）。"
        ;;
      *)
        # 非目标 CUDA 构建（如 +cpu 或 cu130 默认构建）。恢复 torch 时须把配套的
        # torchvision/torchaudio 一并锁回，否则它们会再次把 torch 拉成不匹配版本。
        echo "    [ERROR] torch 被改为 ${TORCH_AFTER}（非 ${CUDA_VERSION} 构建），尝试从 ${CUDA_VERSION} 源恢复 ${TORCH_BEFORE}..."
        if "$PIP" install --no-cache-dir "torch==${TORCH_VERSION}" \
              "torchvision==${TORCHVISION_VERSION}" "torchaudio==${TORCHAUDIO_VERSION}" \
              --index-url "https://download.pytorch.org/whl/${CUDA_VERSION}"; then
          TORCH_RESTORED="$("$PY" -c 'import torch;print(torch.__version__)' 2>/dev/null || echo '?')"
          case "$TORCH_RESTORED" in
            ${TORCH_TARGET_FIRST}*+${CUDA_VERSION}*)
              echo "    torch 已恢复为 ${TORCH_RESTORED}"
              ;;
            *)
              echo "    [ERROR] torch 恢复失败（当前 ${TORCH_RESTORED}）。"
              echo "           这可能因 vLLM 依赖锁定 torch 版本与目标不一致所致。"
              echo "           vLLM 版本与 torch 的对应关系："
              echo "             vllm 0.17~0.19 → torch==2.10.0  |  vllm 0.20+ → torch==2.11.0"
              echo "           请确保 VLLM_VERSION 与 TORCH_VERSION 匹配后重跑。"
              ;;
          esac
        else
          echo "    [ERROR] torch 恢复失败。请重跑本脚本。"
          exit 1
        fi
        ;;
    esac
  fi
  echo "    ms-swift: $("$PY" -c 'import swift;print(getattr(swift, \"__version__\", \"?\"))' 2>/dev/null || echo '?')"
  echo "    vllm:     $("$PY" -m vllm --version 2>/dev/null || echo '?')"

  # ---------- 量化框架（模型压缩向导依赖；按需安装） ----------
  # 每种量化方法需要对应后端框架（缺失时压缩任务会给出明确安装指引）：
  #   bnb → bitsandbytes（默认安装，最常用）；gptq → auto-gptq+optimum；
  #   awq → autoawq；gguf → llama-cpp-python（后三者编译较重，用 --with-quant 全装）
  echo "==> [5.5] 安装量化框架"
  if [ -n "$PIP_INDEX_URL" ]; then
    "$PIP" install --no-cache-dir bitsandbytes --index-url "$PIP_INDEX_URL" || {
      echo "    [WARN] bitsandbytes 安装失败，可稍后执行: bash deploy/ubuntu/install_quant_engines.sh bnb"
    }
  else
    "$PIP" install --no-cache-dir bitsandbytes || {
      echo "    [WARN] bitsandbytes 安装失败，可稍后执行: bash deploy/ubuntu/install_quant_engines.sh bnb"
    }
  fi
  echo "    bitsandbytes: $("$PY" -c 'import bitsandbytes;print(bitsandbytes.__version__)' 2>/dev/null || echo '未安装')"
  if [ "$WITH_QUANT" -eq 1 ]; then
    echo "    安装 GPTQ / AWQ / GGUF 量化框架（编译较重，视网络可能较久）..."
    # auto-gptq/autoawq 编译 CUDA 扩展时需复用 venv 内刚装好的 torch：
    # pip 默认 PEP 517 隔离构建环境不含 torch（报 No module named 'torch'），
    # 故对这类库使用 --no-build-isolation。
    "$PIP" install --no-cache-dir setuptools wheel ninja || true
    if [ -n "$PIP_INDEX_URL" ]; then
      "$PIP" install --no-cache-dir auto-gptq --no-build-isolation --index-url "$PIP_INDEX_URL" || echo "    [WARN] auto-gptq 安装失败（GPTQ 量化不可用，可补装: bash deploy/ubuntu/install_quant_engines.sh gptq）"
      "$PIP" install --no-cache-dir optimum --index-url "$PIP_INDEX_URL" || true
      "$PIP" install --no-cache-dir autoawq --no-build-isolation --index-url "$PIP_INDEX_URL" || echo "    [WARN] autoawq 安装失败（AWQ 量化不可用，可补装: bash deploy/ubuntu/install_quant_engines.sh awq）"
      "$PIP" install --no-cache-dir llama-cpp-python --index-url "$PIP_INDEX_URL" || echo "    [WARN] llama-cpp-python 安装失败（GGUF 导出不可用，可补装: bash deploy/ubuntu/install_quant_engines.sh gguf）"
    else
      "$PIP" install --no-cache-dir auto-gptq --no-build-isolation || echo "    [WARN] auto-gptq 安装失败（GPTQ 量化不可用，可补装: bash deploy/ubuntu/install_quant_engines.sh gptq）"
      "$PIP" install --no-cache-dir optimum || true
      "$PIP" install --no-cache-dir autoawq --no-build-isolation || echo "    [WARN] autoawq 安装失败（AWQ 量化不可用，可补装: bash deploy/ubuntu/install_quant_engines.sh awq）"
      "$PIP" install --no-cache-dir llama-cpp-python || echo "    [WARN] llama-cpp-python 安装失败（GGUF 导出不可用，可补装: bash deploy/ubuntu/install_quant_engines.sh gguf）"
    fi
  fi
else
  echo "    未检测到 GPU：安装 torch CPU 版 + ms-swift（不装 vLLM）；执行模式将设为 mock"
  "$PIP" install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
  if [ -n "$PIP_INDEX_URL" ]; then
    "$PIP" install --no-cache-dir ms-swift --index-url "$PIP_INDEX_URL" || true
  else
    "$PIP" install --no-cache-dir ms-swift || true
  fi
fi
# 清理残缺的 apex 包（transformers 探测到 apex 存在且无 amp 模块时 swift 导入崩溃）
if "$PY" -c "import apex" 2>/dev/null; then
  if ! "$PY" -c "import apex.amp" 2>/dev/null; then
    echo "    [WARN] 检测到残缺的 apex 包，卸载以避免 transformers 导入崩溃"
    "$PIP" uninstall -y apex || true
  fi
fi

# ============================================================
echo "==> [6/9] 构建前端"
cd web-ui
npm install --registry="$NPM_REGISTRY"
npm run build
cd "$PROJECT_ROOT"

# ============================================================
echo "==> [7/9] 生成 backend/.env（如不存在）+ 训练工作目录"
if [ ! -f backend/.env ]; then
  cp deploy/ubuntu/.env.ubuntu backend/.env
  # 无 GPU 时自动降级 mock，保证业务流可跑通；装好 GPU 驱动后可改回 auto
  if [ "$HAS_GPU" -eq 0 ]; then
    sed -i 's/^TRAIN_EXECUTION_MODE=.*/TRAIN_EXECUTION_MODE=mock/' backend/.env
    echo "    已生成 backend/.env（TRAIN_EXECUTION_MODE=mock，因未检测到 GPU）"
  else
    echo "    已生成 backend/.env"
  fi
  echo "    请按需修改 JWT_SECRET_KEY / TRAIN_WORKSPACE"
else
  echo "    backend/.env 已存在，跳过"
fi
mkdir -p backend/workspace/models backend/workspace/datasets
echo "    已创建训练工作目录 backend/workspace（含 models/ datasets/）"

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
if "$PY" deploy/common/seed_demo_data.py --root backend/workspace --samples 200; then
  echo "    演示数据集已生成（backend/workspace/datasets/），后端启动时自动录入数据集管理"
else
  echo "    [WARN] 演示数据集生成失败，可稍后手动执行："
  echo "           $PY deploy/common/seed_demo_data.py --root backend/workspace"
fi

# ============================================================
echo "==> [8/9] 验证后端模块导入"
cd backend
"$PY" test_import.py

# ============================================================
echo "==> [9/9] 安装说明汇总"
echo ""
echo "============================================================"
echo "初始化完成！"
if [ "$HAS_GPU" -eq 1 ]; then
  echo "  GPU 环境：TRAIN_EXECUTION_MODE=auto，装好模型后即可真实训练/推理"
else
  echo "  CPU 环境：TRAIN_EXECUTION_MODE=mock（业务流可跑通）；"
  echo "           装好 NVIDIA 驱动后改回 auto 并重跑本脚本即可升级为真实模式"
fi
echo "------------------------------------------------------------"
echo "立即启动（前台）：cd $PROJECT_ROOT && bash deploy/ubuntu/start.sh"
echo "后台常驻 + 开机自启（推荐服务器）：bash deploy/ubuntu/install_systemd.sh [--with-nginx]"
echo "下载真实模型：bash deploy/common/download_models.sh --model Qwen/Qwen2.5-0.5B-Instruct"
echo "重新生成演示数据集：backend/.venv/bin/python deploy/common/seed_demo_data.py --root backend/workspace"
echo "访问地址：http://<服务器IP>:8000（或 Nginx 80 端口）"
echo "默认账号：admin / admin123（启动后请尽快修改）"
echo "============================================================"
