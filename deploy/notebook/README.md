# LLM 训推平台 · 部署指南（ModelScope Notebook / Ubuntu 24.04 服务器）

本指南覆盖平台的两种部署方式，任选其一（**均无需 Docker**，整个项目前后端一体运行在单一主机上）：

| 路径 | 环境 | 依赖服务 | 业务服务 | 文档 |
|---|---|---|---|---|
| **A. Notebook 直跑（推荐免费体验）** | ModelScope 免费 GPU Notebook（无 Docker） | apt 装 MySQL + Redis（MinIO 省略，自动降级本地磁盘） | FastAPI 托管前后端，`uvicorn` 单进程 | 本文档「三」 |
| **C. Ubuntu 24.04 服务器** | 全新 Ubuntu 24.04（systemd，Python 3.12 + PEP 668） | apt + systemd 装 MySQL + Redis | FastAPI 直跑 或 systemd 常驻 + Nginx 80 | `deploy/ubuntu/README.md`（本文档「四」摘要） |

> **真实训练/推理（MS-Swift + vLLM）必须在 GPU 宿主机直接执行**（本项目 executor 以 `subprocess` 本机调用 swift/vllm，不依赖容器），因此：
> - 路径 A：天然满足，装好引擎后 `TRAIN_EXECUTION_MODE=auto` 自动走真实执行；
> - 路径 C：GPU 机器同样天然满足；无 GPU 机器自动降级 mock。
>
> 两种方式都是**前后端一体**部署：前端 SPA 由 FastAPI 直接托管（`FRONTEND_DIST_DIR=../web-ui/dist`），
> MySQL/Redis 本机 apt 安装（systemd 自启），不存在把前后端或各服务拆分到不同服务器的场景。

## 一、快速开始（TL;DR）

```bash
# —— 路径 A：ModelScope Notebook（免费 GPU）——
# 1) 本地打包上传 zip（Windows 项目根目录）
powershell -ExecutionPolicy Bypass -File deploy/common/package.ps1
# 2) Notebook 终端
unzip model_train_upload.zip && cd model_train
bash deploy/notebook/init_env.sh            # 初始化（装 MySQL/Redis/引擎/前端）
bash deploy/notebook/start.sh --background  # 启动（8000 端口，控制台做端口映射）

# —— 路径 C：全新 Ubuntu 24.04 服务器 ——
bash deploy/ubuntu/init_env.sh                              # 初始化（venv + 引擎 + 前端 + DB）
bash deploy/ubuntu/install_systemd.sh --with-nginx          # systemd 常驻 + 80 端口（推荐）
```

默认账号：`admin / admin123`，**首次登录后立即修改**。

## 二、执行模式说明（auto / mock / real）

`backend/.env` 中 `TRAIN_EXECUTION_MODE`：

| 值 | 行为 |
|---|---|
| `auto`（默认） | **同时满足**「`swift` 命令已安装」**且**「`nvidia-smi` 探测到可用 GPU」才真实执行，否则 mock。无 GPU / 未装驱动 / 未装引擎均安全降级 |
| `mock` | 本地模拟执行（产出日志/指标/模型产物），用于无 GPU 环境验证完整链路 |
| `real` | 强制真实执行（无 swift / 无 GPU 时命令本身会失败） |

## 三、路径 A：ModelScope Notebook 免费 GPU 环境

> **已验证镜像**：`ubuntu22.04-cuda12.8.1-py312-torch2.10.0-1.39.0`
> （Ubuntu 22.04 / CUDA 12.8.1 / Python 3.12 / torch 2.10.0 / 预装 ModelScope Library；**无 Docker**、默认**无 Node.js**）

### 1. 把代码传上 Notebook（代码只在本地、无 git 仓库时，三选一）

**方式一：本地打包 → 网页拖拽上传（最简单，先用这个）**

Windows 下，在项目根目录执行（自动排除 `node_modules` / `tmp` / `dist` / `storage` / 日志 / `backend/.env` 等，仅几 MB）：

```powershell
powershell -ExecutionPolicy Bypass -File deploy/common/package.ps1
```

生成 `model_train_upload.zip`（内含 `model_train/` 目录）后，在 Notebook 文件管理界面把 zip 拖拽上传，终端解压：

```bash
unzip model_train_upload.zip && cd model_train   # unzip 缺失时：sudo apt-get install -y unzip
```

**方式二：ModelScope 数据集仓库中转（推荐迭代场景，改动可反复同步）**

本地与 Notebook 都装 `modelscope`，把 zip 放进自己的数据集仓库：

```bash
# 本地（Windows PowerShell 或任意终端）
pip install modelscope
modelscope upload --dataset <你的账号>/<仓库名> model_train_upload.zip .

# Notebook 内
pip install modelscope
modelscope download --dataset <你的账号>/<仓库名> local_dir ./
unzip model_train_upload.zip && cd model_train
```

仓库本身也是 git 仓库，同样支持 `git clone` / `git push` 方式同步。

**方式三：网盘中转（兜底）**

上传到任意支持直链下载的网盘，Notebook 里 `wget <直链>` 下载后解压。

### 2. 一键初始化

```bash
bash deploy/notebook/init_env.sh
```

脚本流程（共 8 步，已在镜像 `ubuntu22.04-cuda12.8.1-py312-torch2.10.0-1.39.0` 上适配；可选环境变量 `PIP_INDEX_URL` / `NPM_REGISTRY` 指定镜像源）：

1. **环境自检**：GPU（`nvidia-smi`）→ Python（要求 ≥3.10）→ Node（缺失或 <18 时自动装 Node 20）→ 磁盘空间预检（安装引擎需 ≥12GB）→ modelscope 库校验（缺失自动补装）；
2. 安装 MySQL + Redis（apt，免 Docker）；
3. 启动 MySQL/Redis 并执行 `deploy/mysql/init.sql` 建库建用户（Notebook 容器无 systemd 时自动降级用 `mysqld_safe`/`redis-server` 手动拉起进程）；
4. 安装后端 Python 依赖（已兼容 py312）；
5. 安装 MS-Swift + vLLM：直接安装最新版（不再固定 `ms-swift==2.5.1`——其与 torch 2.10/py312 时代错位）；安装后自动校验 torch 未被改动，若被 vLLM/ms-swift 依赖解析降级则自动从 cu128 index 恢复，恢复失败直接退出；并清理残缺 apex 包、校验 vllm import；
6. 构建前端 `web-ui/dist`（npm install + npm run build）；
7. 生成 `backend/.env`（不存在时从 `.env.notebook` 复制）+ 自动创建训练工作目录 `backend/workspace/{models,datasets}`；
8. 验证后端模块导入。

### 3. 启动服务（前端由 FastAPI 直接托管，单端口 8000）

```bash
bash deploy/notebook/start.sh
#    可选 --worker           同时启动 Celery Worker（任务独立进程，API 重启不中断）
#    可选 --port=9000        指定端口
#    可选 --background       后台运行（日志 backend/api.log，PID backend/api.pid）
#    可选 --stop / --restart 停止 / 重启后台 API
```

### 4. 对外访问

1. 后端默认监听 `0.0.0.0:8000`；
2. 在魔搭控制台找到 Notebook 的 **端口映射**，添加 `8000` → 生成公网地址；
3. 浏览器打开生成的地址即可访问前端（同域 `/api`、`/ws` 已打通，无需额外配置）。

默认账号：`admin / admin123`，**首次登录后立即修改**（公网可访问）。

### 5. 默认模型（部署时自动下载并录入模型库）与真实模型下载

**平台不再内置演示种子模型**（旧版占位路径会导致真实训练前置检查失败）。`init_env.sh` 已内置**默认小模型自动安装**：

- 默认下载 **Qwen/Qwen2.5-0.5B-Instruct**（约 1GB）到 `backend/workspace/models/`，并**模拟页面「创建模型 + 上传模型文件」逻辑自动录入模型库**（写入 `models / model_versions / model_files`，`storage_path` 与文件记录指向真实下载路径），「我的模型库 / 模型库广场」立即可见，可直接用于微调/推理演示；
- 更换模型：修改 `backend/.env` 的 `SEED_MODEL_ID`（ModelScope 模型 ID，留空 = 不自动安装）后重跑 `bash deploy/notebook/init_env.sh`；
- 手动安装：`bash deploy/common/download_models.sh --model <模型ID>` 下载后**自动录入模型库**（幂等，无需重启后端）。

> 0.5B 小模型可在无 GPU 机器上用 CPU 跑通演示链路；真实训练/推理建议按需下载更大模型。

**演示数据集（自动生成，训练向导开箱可选）**：`init_env.sh` 会执行
`python3 deploy/common/seed_demo_data.py`，在 `backend/workspace/datasets/` 下生成三个
演示数据集（ModelScope 下载 `swift/self-cognition` 并派生），后端启动时自动录入「数据集管理」：

| 目录 | data_type | 用途 | 格式 |
|---|---|---|---|
| `sft_self_cognition` | SFT | 微调 / 场景训练 | 对话式 conversations |
| `preference_demo` | DPO | 对齐（DPO/KTO/ORPO/SimPO） | chosen / rejected 偏好对 |
| `pretrain_demo` | CPT | 预训练（swift pt） | `{"text": "..."}` |

手动重新生成：`python3 deploy/common/seed_demo_data.py --root backend/workspace [--samples 200] [--force]`。

按需下载其他真实模型 / 数据集（`download_models.sh` 会把模型下载到 `backend/workspace/models/` 并**自动录入模型库**）：

```bash
# 模型下载完成后自动录入模型库（我的模型库 / 模型库广场可见）
bash deploy/common/download_models.sh --model Qwen/Qwen2.5-0.5B-Instruct
#   数据集：--dataset swift/self-cognition（数据集仍需手动指向 storage_path）
#   一次多个：--model A --model B
#   自定义目录：--dir models/qwen/qwen2.5-0.5b-instruct
```

> 模型无需手动编辑 `storage_path`（自动录入时已指向真实下载路径）；数据集下载后需在平台「数据集管理」
> 把 `storage_path` 改为脚本打印的绝对路径。若录入时 MySQL 未就绪，脚本会打印可补录的命令，重跑下载脚本即可（幂等）。

### 6. 备份与恢复

```bash
# 备份数据库 + 训练产物（mysqldump + workspace/storage 打包到 backend/backups/）
bash deploy/common/backup.sh
#   仅备份数据库：--no-data   自定义目录：--out /path

# 把 backups/ 下载到本地，或上传 ModelScope 数据集仓库中转
modelscope upload --dataset <你的账号>/<仓库名> backend/backups backups
```

实例重建恢复：重新 `unzip` + `bash deploy/notebook/init_env.sh`，再把 `backups/` 拷回并解压即可。

## 四、路径 C：全新 Ubuntu 24.04 服务器

**详细指南见 [`deploy/ubuntu/README.md`](./../ubuntu/README.md)**，要点摘要：

- **差异适配**：Ubuntu 24.04 默认 Python 3.12 且 PEP 668 禁止系统 pip → 依赖统一装到独立 venv `backend/.venv`；MySQL/Redis 走 apt + systemd 开机自启（**无需 Docker**，有无 Docker 均不影响）；Node 走 NodeSource 20；
- **GPU 处理**：检测到 NVIDIA GPU（`nvidia-smi`）→ 安装 torch cu128 + ms-swift + vLLM，`auto` 真实执行；无 GPU → 自动降级 `mock`，业务流可跑通；
- **初始化**：`bash deploy/ubuntu/init_env.sh`（9 步，约 15~30 分钟，幂等可重跑）；
- **启动**：验证用 `bash deploy/ubuntu/start.sh`；服务器长期运行推荐 `bash deploy/ubuntu/install_systemd.sh --with-nginx`（systemd 常驻 + 80 端口反代 + WebSocket）；
- **驱动注意**：cu128 需要 NVIDIA 驱动 ≥ 570；驱动较旧时 `CUDA_VERSION=cu124 TORCH_VERSION=2.9.0 bash deploy/ubuntu/init_env.sh`。

## 五、端口与服务清单

| 端口 | 服务 | 说明 |
|---|---|---|
| 8000 | FastAPI + 前端 SPA（路径 A / C） | 前后端一体，含 `/api`、`/static`、`/assets` |
| 80 | Nginx（路径 C 可选） | 反代到 8000 + WebSocket |
| 3306 | MySQL | 库 `llm_train`，用户 `llm_train/llm_train_2026` |
| 6379 | Redis | Celery broker/backend |

## 六、数据持久化（重要）

- **Notebook 实例释放后数据全部丢失**（磁盘不保留），请务必：
  1. **模型产物**：训练结束后用 `modelscope upload` 回传 ModelScope 仓库，或下载到本地；
  2. **数据库**：定期 `bash deploy/common/backup.sh`（或手动 `mysqldump -u llm_train -p llm_train > backup.sql`）并下载；
  3. **代码**：每次改动后重新 `deploy/common/package.ps1` 打包上传，或维护一个 ModelScope 数据集仓库做代码中转；实例重建后 `unzip` + `bash deploy/notebook/init_env.sh` 即可恢复运行环境。
- **Ubuntu 服务器**：磁盘持久，但建议同样定期 `bash deploy/common/backup.sh` 并异地备份（backups/ 目录）。

## 七、常见问题

- **`swift` 命令找不到**：确认 `pip install ms-swift` 成功（Ubuntu 24.04 用 `backend/.venv/bin/python -m pip`）；`TRAIN_EXECUTION_MODE=auto` 且无 GPU 时会自动降级 mock，方便先验证业务流程。
- **MS-Swift 与 torch 版本冲突**：镜像预装 torch 2.10.0 + CUDA 12.8.1（py312）。`ms-swift==2.5.1`（2024-11）与 torch 2.10/py312 时代错位，其依赖（transformers/trl 等）解析到最新版后运行期易崩，`init_env.sh` 第 5 步已改为**直接安装最新版 ms-swift**（3.x/4.x 官方支持 py312）。安装后会校验 torch：若被 vLLM/ms-swift 依赖解析降级，自动从 cu128 index 恢复（`pip install "torch==<原版本>" --index-url https://download.pytorch.org/whl/cu128`），恢复失败直接退出；也可手动确认 `python3 -c "import torch;print(torch.__version__)"`（Ubuntu 24.04 加 venv 路径）。
- **Node.js / npm 不存在**：镜像默认无 Node；`init_env.sh` 第 1 步会自动通过 NodeSource 安装 Node 20（新版 gpg keyring + apt 源方式，失败自动回退旧 setup 脚本）。若网络受限装不上，手动装 Node 20+ 后重跑脚本。
- **Python 3.12 依赖安装失败**：后端依赖（asyncmy / celery 等）均有 py312 轮子；若个别包编译失败，先 `python3 -m pip install --upgrade pip` 再重跑 `init_env.sh`。Ubuntu 24.04 出现 `externally-managed-environment` 是 PEP 668 限制，请使用 venv（`backend/.venv`）。
- **AMD（ROCm）192G 环境**：MS-Swift 对 ROCm 支持有限、vLLM 不支持 ROCm，**请选择 NVIDIA 24G 环境**跑训练/推理。
- **`ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock'` / MySQL 启动失败**：Notebook 容器内通常没有 systemd，`service`/`systemctl` 都拉不起 MySQL（Ubuntu 22.04 的 mysql-server 也不带 `/etc/init.d/mysql`）。`init_env.sh`/`start.sh` 已自动兜底：补齐 `/var/run/mysqld` 目录、数据目录缺失时自动 `mysqld --initialize-insecure`、再用 `mysqld_safe --user=mysql` 手动拉起进程，并等待就绪（失败会打印 `/var/log/mysql/error.log` 诊断后退出）。若仍失败，手动执行：
  ```bash
  sudo mkdir -p /var/run/mysqld && sudo chown mysql:mysql /var/run/mysqld
  sudo mysqld_safe --user=mysql &        # 日志：/tmp/mysqld_safe.log、/var/log/mysql/error.log
  sleep 5 && sudo mysqladmin ping        # 期望输出 mysqld is alive
  ```
  数据目录损坏（初始化后仍起不来）时：`sudo rm -rf /var/lib/mysql && sudo mysqld --initialize-insecure`，再重跑 `init_env.sh`。Ubuntu 24.04 服务器一般走 systemd：`sudo systemctl status mysql`。
- **`Data too long for column 'operator_version'`（ERROR 1406）**：`train_tasks.operator_version` / `deployments.operator_version` 存的是算子**版本 ID（32 位 UUID）**，旧列宽 `VARCHAR(20)` 不够导致插入失败。代码已改为 `VARCHAR(36)`，新实例建表即正确；**已存在的旧库**需手工加宽一次（或重启 API 让 `schema_sync` 自动"只扩不缩"同步）：
  ```sql
  ALTER TABLE train_tasks MODIFY COLUMN operator_version VARCHAR(36) COMMENT '算子版本ID';
  ALTER TABLE deployments MODIFY COLUMN operator_version VARCHAR(36) COMMENT '算子版本ID';
  ```
- **提交报 400「超参取值不在允许范围」**：算子版本的参数契约（`start_params` 的 `choices`）限制了取值，而训练表单为演示模式锁定了默认值（如预训练/对齐默认 `learning_rate=1e-5`，而默认契约 choices 不含该值）。两种解法任选：
  1. 编辑该算子版本的「启动参数」契约 JSON，把 `learning_rate.choices` 改为 `[1e-5, 5e-05, 0.0001, 0.0005]`，或直接删掉 `choices` 只留 `default`（不限制取值）；
  2. 重新打包上传后，新创建的算子版本默认契约已包含 `1e-5`。
  注：`choices` 校验按数值比较（字符串 `'5e-5'` 与浮点 `5e-05` 视为相等），无需担心科学计数法写法差异。
- **训练功能为最小化演示版，与完整能力的差异**：
  1. **场景训练已简化为单阶段 SFT**：向导仍选场景标签，实际按 `swift sft` 执行一次（第 1 阶段语义）；
  2. **对齐仅支持 DPO/KTO/ORPO/SimPO 离线方法**，RLHF(PPO) 因需要奖励/参考模型暂不提供（页面已移除选项）；
  3. **压缩仅支持量化**（`swift export`，方法 bnb/gptq/awq/gguf），剪枝/蒸馏暂不提供；量化位数仅 4/8（非法值会在提交/执行时明确报错）；
  4. **默认模型为 0.5B 级**（`Qwen/Qwen2.5-0.5B-Instruct`，部署脚本自动下载录入），未选基础模型时不再回退 7B；
  5. **资源参数（资源池/GPU数量/CPU/内存）仅展示入库**，实际执行按宿主机真实资源（单卡）运行。
- **ms-swift 4.x 参数名自动适配**：适配器在执行前探测 `swift --help` 与各子命令 `--help`，按实际安装版本适配参数名
  （如 `--model`→`--model_id_or_path`、`--tuner_type`→`--train_type`、`--lora_target_modules`→`--target_modules`、
  下划线/连字符形式），并在 4.x 移除 `swift rlhf/pt` 等子命令时尝试候选替代（`sft/train`）。
  若某任务仍报参数错误，执行 `swift <子命令> --help 2>&1 | grep -oE -- '--[a-z][a-z0-9_-]*' | sort -u` 核对后反馈。
- **量化报「量化方法 GPTQ/AWQ 需要校准数据集」**：GPTQ/AWQ 量化必须选择校准数据集（可用演示数据集
  `sft_self_cognition`）；改用 `bnb` 量化则无需校准数据。
- **`ImportError: cannot import name 'amp' from 'apex'`（swift 启动即崩）**：环境里装到了残缺的 `apex` 包（PyPI 同名旧包或半成品安装，只有 `__init__.py` 没有 `amp` 模块）。transformers 探测到 `apex` 存在就尝试 `from apex import amp`，导致 swift 进程导入崩溃；训练本身不需要 apex。执行 `python3 -m pip uninstall -y apex` 后重新提交任务即可（`init_env.sh` 第 5 步已自动检测并清理此类残缺 apex）。
- **任务提交后 5 秒左右"收到取消信号，终止训练进程"**：该任务之前点过"取消/停止"留下的 `cancel` 控制信号（Redis `train:control:<task_id>`，24h TTL）在重新提交后仍残留，executor 启动即读到并终止进程。`redis-cli DEL train:control:<task_id>`（或新建任务提交）即可；新版 executor 在每次执行开始时自动清空历史控制信号，无需再手动处理。
- **`pt.py: error: ambiguous option: --model`（swift 启动即报参数错误）**：`swift pt` 的模型参数名是 `--model_id_or_path`（别名 `--model-id-or-path`），**并没有 `--model`**（2.5.1 与 3.x 皆如此，`swift sft` 文档示例与 `swift pt` 实际参数不一致），平台按 `--model` 生成命令导致 argparse 前缀匹配歧义。新版适配器会**自动探测当前 swift 版本**（解析 `swift pt --help` 的选项集）并适配参数名（`--model`→`--model_id_or_path`、`--a_b`→`--a-b` 连字符形式），无需手动指定；探测失败时回退默认名。确认当前参数：`swift pt --help 2>&1 | grep -oE -- '--model[a-z0-9_-]*' | sort -u`。
- **推理服务启动失败：`ModuleNotFoundError: vllm.entrypoints.openai.api_server`**：新版 vLLM（>=0.6）已弃用该入口并统一到 `vllm serve`。平台适配器会自动探测 `vllm --help`：存在 `serve` 子命令时改用 `vllm serve <模型路径> --port <端口>`，探测失败才回退旧入口。若手动使用旧命令，请改用 `vllm serve`。
- **真实训练报 swift 内部错误（如 `set_model_type` / 找不到 config.json / 尝试联网下载）**：模型/数据集的 `storage_path` 指向了磁盘上不存在的目录（未下载或未配置）。真实训练（`TRAIN_EXECUTION_MODE=auto/real`）要求模型与数据集路径真实存在：先 `bash deploy/common/download_models.sh --model <模型id>` 下载模型（下载后自动录入模型库、`storage_path` 已指向真实路径，无需手动改）、准备 JSONL 数据集文件，再在平台里把数据集的 `storage_path` 改为真实路径。执行器已加**启动前前置检查**，路径缺失会直接报"模型/数据集路径不存在"的明确错误，不再抛 swift 内部 traceback。只想先验证业务流程时，把 `backend/.env` 的 `TRAIN_EXECUTION_MODE` 改为 `mock` 并重启 API，任务即走模拟执行（产出日志/指标/模型），无需真实数据。
- **任务不执行 / 一直 pending**：确认 Redis 已启动（`redis-cli ping`）；未启动时任务会在 API 进程内自动执行（`--worker` 才需要 Redis）。
- **Ubuntu 24.04 专属问题**（PEP 668 / NVIDIA 驱动版本 / 防火墙 / systemd）：见 [`deploy/ubuntu/README.md`](./../ubuntu/README.md)「常见问题」。
