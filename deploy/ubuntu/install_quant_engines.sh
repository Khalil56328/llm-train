#!/usr/bin/env bash
# ============================================================
# LLM 训推平台 · 量化框架补装脚本（模型压缩向导依赖）
#
# 用法：
#   bash deploy/ubuntu/install_quant_engines.sh [bnb|gptq|awq|gguf|all]
#     bnb   → bitsandbytes（4/8bit 量化）
#     gptq  → auto-gptq + optimum（GPTQ 量化）
#     awq   → autoawq（AWQ 量化）
#     gguf  → llama-cpp-python（GGUF 导出）
#     all   → 全部安装（默认）
#
# 说明：
#   - 需要 GPU + CUDA 环境（CPU mock 模式无需量化框架）；
#   - 安装到 backend/.venv，与 init_env.sh 保持同一环境；
#   - 已部署环境缺哪个量化库、补装哪个即可；平台压缩任务启动前也会
#     自动预检依赖并给出安装指引，无需手动排查。
#
# 环境变量：
#   PIP_INDEX_URL    pip 镜像源（国内网络可设 https://pypi.tuna.tsinghua.edu.cn/simple）
# ============================================================
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

PY="$PROJECT_ROOT/backend/.venv/bin/python"
PIP="$PROJECT_ROOT/backend/.venv/bin/pip"
if [ ! -x "$PY" ]; then
  echo "[ERROR] 未找到 backend/.venv，请先执行 deploy/ubuntu/init_env.sh 初始化环境"
  exit 1
fi

TARGET="${1:-all}"
PIP_INDEX_URL="${PIP_INDEX_URL:-}"

_install() {
  if [ -n "$PIP_INDEX_URL" ]; then
    "$PIP" install --no-cache-dir "$@" --index-url "$PIP_INDEX_URL"
  else
    "$PIP" install --no-cache-dir "$@"
  fi
}

# auto-gptq / autoawq 需编译 CUDA 扩展，构建脚本要求环境中已装 torch。
# 注意：pip 默认的 PEP 517 隔离构建环境【不含】torch（即使 venv 里已装），
# 直接安装会报 "Building cuda extension requires PyTorch ... No module named 'torch'"。
# 因此对这类库使用 --no-build-isolation，复用 venv 内已安装的 torch 与编译工具链。
_install_cuda_ext() {
  if [ -n "$PIP_INDEX_URL" ]; then
    "$PIP" install --no-cache-dir "$@" --no-build-isolation --index-url "$PIP_INDEX_URL"
  else
    "$PIP" install --no-cache-dir "$@" --no-build-isolation
  fi
}

# 前置检查：编译型量化库（gptq/awq/gguf）需要 venv 内存在 torch（部署引擎时已装）
if [ "$TARGET" != "bnb" ]; then
  if ! "$PY" -c "import torch" 2>/dev/null; then
    echo "[ERROR] backend/.venv 未检测到 torch。"
    echo "        auto-gptq / autoawq / llama-cpp-python 的构建依赖 torch，"
    echo "        请先执行 deploy/ubuntu/init_env.sh 完成引擎安装，或确认 torch 已装入 backend/.venv。"
    exit 1
  fi
fi

case "$TARGET" in
  bnb)
    echo "==> 安装 bitsandbytes（bnb 4/8bit 量化）..."
    _install bitsandbytes
    ;;
  gptq)
    echo "==> 安装 auto-gptq + optimum（GPTQ 量化；编译 CUDA 扩展，视网络可能较久）..."
    # 先补齐构建工具链，再以 --no-build-isolation 复用 venv 内的 torch 编译
    _install setuptools wheel ninja
    _install_cuda_ext auto-gptq
    _install optimum
    ;;
  awq)
    echo "==> 安装 autoawq（AWQ 量化；编译 CUDA 扩展，视网络可能较久）..."
    _install setuptools wheel ninja
    _install_cuda_ext autoawq
    ;;
  gguf)
    echo "==> 安装 llama-cpp-python（GGUF 导出；从源码构建需要 cmake，视网络可能较久）..."
    if command -v cmake >/dev/null 2>&1; then
      _install_cuda_ext llama-cpp-python
    else
      echo "    [WARN] 未检测到 cmake，llama-cpp-python 需从源码构建（依赖 CMake）。"
      echo "          可先执行: sudo apt-get install -y cmake，再重试本脚本。"
      _install llama-cpp-python || true
    fi
    ;;
  all)
    echo "==> 安装全部量化框架（bitsandbytes / auto-gptq / autoawq / llama-cpp-python）..."
    _install bitsandbytes
    _install setuptools wheel ninja
    _install_cuda_ext auto-gptq
    _install optimum
    _install_cuda_ext autoawq
    if command -v cmake >/dev/null 2>&1; then
      _install_cuda_ext llama-cpp-python
    else
      echo "    [WARN] 未检测到 cmake，llama-cpp-python 需从源码构建（依赖 CMake）。"
      echo "          可先执行: sudo apt-get install -y cmake，再执行: bash deploy/ubuntu/install_quant_engines.sh gguf"
      _install llama-cpp-python || true
    fi
    ;;
  *)
    echo "用法: bash deploy/ubuntu/install_quant_engines.sh [bnb|gptq|awq|gguf|all]"
    echo ""
    echo "模型压缩向导支持的量化方法与依赖框架："
    echo "  bnb  → bitsandbytes"
    echo "  gptq → auto-gptq optimum"
    echo "  awq  → autoawq"
    echo "  gguf → llama-cpp-python"
    exit 1
    ;;
esac

echo ""
echo "完成。可在平台「模型压缩」向导重新发起任务；"
echo "若仍有依赖缺失，任务日志会直接给出对应的安装命令。"
