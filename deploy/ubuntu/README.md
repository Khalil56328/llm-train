# LLM 训推平台 · Ubuntu 24.04 全新服务器部署指南

> 适用：**一台刚申请到的全新 Ubuntu 24.04 系统**（云服务器 / 物理机均可）。
> 与 ModelScope Notebook 的差异：系统自带 systemd、默认 Python 3.12 且 **PEP 668 禁止向系统 Python 直接 pip 安装**（本方案统一使用独立 venv `backend/.venv`）、apt 自带 Node 18 无 npm（本方案装 NodeSource Node 20）。

## 〇、环境要求

| 项目 | 要求 |
|---|---|
| 系统 | Ubuntu 24.04 LTS（x86_64），root 或可 sudo 的用户 |
| 磁盘 | ≥ 30GB 可用（torch + MS-Swift + vLLM 约 10~15GB，模型另算） |
| 内存 | ≥ 16GB（训练/推理按模型大小另行评估） |
| GPU（可选） | NVIDIA 显卡 + 驱动 ≥ 570（支持 CUDA 12.8）；无 GPU 可先以 **mock 模式**跑通业务流 |
| 网络 | 能访问 apt / pypi / npm / GitHub 或国内镜像 |

## 一、部署形态选择

| 形态 | 命令 | 适合 |
|---|---|---|
| **A. 前台直跑**（最简单） | `bash deploy/ubuntu/start.sh` | 验证 / 临时使用 |
| **B. systemd 常驻（推荐）** | `bash deploy/ubuntu/install_systemd.sh --with-nginx` | 服务器长期运行：开机自启、崩溃自动拉起、80 端口对外 |

> 本方案**无需 Docker**（有无 Docker 均不影响）：MySQL/Redis 由 apt 原生安装并 systemd 自启，
> 前端由 FastAPI 直接托管，整个项目（前端 + API + Worker）前后端一体运行在 GPU 宿主机上。
> 真实训练/推理（MS-Swift + vLLM）**必须在 GPU 宿主机直接执行**，本方案天然满足；
> 无 GPU 的机器自动走 mock 模式（业务全流程可验证，不产生真实训练）。

## 二、部署步骤

### 1. 把代码放到服务器（三选一）

```bash
# 方式一：git clone（项目有仓库时）
git clone <仓库地址> && cd model_train

# 方式二：本机打包 → scp（Windows 本机执行 deploy/notebook/package.ps1 生成 model_train_upload.zip）
# Windows: powershell -ExecutionPolicy Bypass -File deploy/notebook/package.ps1
scp model_train_upload.zip <用户>@<服务器IP>:~/
unzip model_train_upload.zip && cd model_train

# 方式三：ModelScope 数据集仓库中转（同 Notebook 方式，见 deploy/notebook/README.md）
```

### 2. 一键初始化（需 root/sudo，约 15~30 分钟）

```bash
bash deploy/ubuntu/init_env.sh
```

脚本 9 步流程：

1. **环境自检**：OS / GPU（`nvidia-smi`）/ Python 3.12 / 磁盘空间；
2. **系统依赖**：`mysql-server`、`redis-server`、构建工具、`python3-venv`（PEP 668 必须）、NodeSource Node 20；
3. **启动 MySQL / Redis 并建库**（复用 `deploy/mysql/init.sql`；Ubuntu 走 systemd，root 走 auth_socket 免密）；
4. **创建 venv 并安装后端依赖**（`backend/.venv`，全部依赖装在 venv 内，不污染系统 Python）；
5. **安装引擎**：
   - 有 GPU：`torch==2.10.0`（cu128，与已验证 Notebook 镜像对齐）+ `ms-swift` + `vllm`，并校验 torch 未被依赖解析降级（自动从 cu128 index 恢复）；
   - 无 GPU：`torch`（CPU 版）+ `ms-swift`，并把生成的 `.env` 中 `TRAIN_EXECUTION_MODE` 设为 `mock`；
6. **构建前端**（npm install + npm run build → `web-ui/dist`）；
7. **生成 `backend/.env`**（从 `.env.ubuntu` 复制）+ 创建 `backend/workspace/{models,datasets}`；
8. **验证后端模块导入**（`test_import.py`）；
9. 打印后续操作指引。

> **无 GPU / 驱动未装**：`nvidia-smi` 不可用时会自动降级 mock 并提示。装好驱动（`sudo ubuntu-drivers autoinstall` 后重启，或 `--install-driver` 参数自动装）后，改回 `backend/.env` 的 `TRAIN_EXECUTION_MODE=auto` 并重跑 `init_env.sh` 即可升级为真实模式。
>
> **驱动版本注意**：CUDA 12.8（cu128）需要驱动 ≥ 570。驱动较旧（如 550~570）时改用 `CUDA_VERSION=cu124 TORCH_VERSION=2.9.0 bash deploy/ubuntu/init_env.sh`。

### 3. 下载真实模型（真实训练/推理必需）

平台内置的种子模型/数据集是**演示占位符**，真实训练前请下载模型与数据集并把 `storage_path` 改为真实路径：

```bash
# 下载模型到 backend/workspace/models/，脚本会打印应填入平台的绝对路径
bash deploy/notebook/download_models.sh --model Qwen/Qwen2.5-7B-Instruct
# 一次多个：--model A --model B
# 数据集：--dataset swift/self-cognition
# 指定落盘目录：--dir models/qwen/qwen2.5-7b-instruct
```

然后在平台「模型管理 / 数据集管理」编辑该模型/数据集的 `storage_path` 为脚本打印的绝对路径。

### 4. 启动服务

```bash
# 形态 A：前台启动（前端由 FastAPI 托管，单端口 8000）
bash deploy/ubuntu/start.sh
#    --worker     同时启动 Celery Worker
#    --port=9000  指定端口
#    --background 后台运行（日志 backend/api.log，停止：--stop）

# 形态 B（推荐）：systemd 常驻 + Nginx（80 端口）
bash deploy/ubuntu/install_systemd.sh --with-nginx
```

### 5. 访问与账号

| 形态 | 访问地址 |
|---|---|
| A（默认 8000） | `http://<服务器IP>:8000/` |
| B（Nginx 80） | `http://<服务器IP>/` |

默认账号：`admin / admin123`，**首次登录后立即修改**。
云服务器记得在安全组/防火墙放行对应端口：`sudo ufw allow 80/tcp`（或 8000）、`3306`（仅内网）。

## 三、常用运维

```bash
# systemd 服务状态与日志
sudo systemctl status llm-train-api
sudo journalctl -u llm-train-api -f

# 卸载 systemd 服务（不删代码）
bash deploy/ubuntu/install_systemd.sh --remove

# 数据备份（服务器磁盘持久，但建议定期备份 + 异地/对象存储）
bash deploy/notebook/backup.sh          # mysqldump + workspace/storage 打包到 backend/backups/

# 升级引擎（如 ms-swift 出新版）
cd backend && .venv/bin/pip install -U ms-swift vllm
```

## 四、端口与服务清单

| 端口 | 服务 | 说明 |
|---|---|---|
| 80 | Nginx（形态 B） | 反代到 8000，含 WebSocket |
| 8000 | FastAPI + 前端 SPA（形态 A/B） | 前后端一体，含 `/api`、`/static`、`/assets` |
| 3306 | MySQL | 库 `llm_train`，用户 `llm_train/llm_train_2026` |
| 6379 | Redis | Celery broker/backend |

## 五、常见问题

- **`error: externally-managed-environment`（PEP 668）**：Ubuntu 24.04 禁止向系统 Python pip 安装。一律使用 `backend/.venv`：`cd backend && .venv/bin/python -m pip install ...`（`init_env.sh` / `start.sh` / systemd 均已自动使用 venv）。
- **MySQL 连不上 / `ERROR 2002`**：`sudo systemctl status mysql`；Ubuntu root 走 auth_socket，初始化用 `sudo mysql < deploy/mysql/init.sql` 即可。
- **`nvidia-smi` 不存在（无 GPU 或驱动未装）**：`sudo ubuntu-drivers autoinstall` 后重启；或用 `--install-driver` 参数自动安装。未装驱动前平台自动 mock，业务流不受影响。
- **vLLM 启动报 CUDA 错误 / 驱动版本不足**：cu128 需要驱动 ≥ 570。驱动较旧时重跑 `CUDA_VERSION=cu124 TORCH_VERSION=2.9.0 bash deploy/ubuntu/init_env.sh`。
- **80 端口被占（Nginx 默认站点）**：`install_systemd.sh --with-nginx` 会自动停用默认站点；若手动配置，删除 `/etc/nginx/sites-enabled/default` 后 `sudo nginx -t && sudo systemctl reload nginx`。
- **云服务器访问不通**：检查安全组入方向规则与 `sudo ufw status`（放行 `80/tcp` 或 `8000/tcp`）。
- **构建前端失败**：确认 Node ≥ 18（`node -v`）；apt 自带的 nodejs 18 不带 npm，请用 NodeSource 20（脚本已自动安装）。
- **任务提交后一直 pending**：`redis-cli ping` 应返回 PONG；Redis 未启动时任务会自动降级为 API 进程内执行（仅 `--worker` 模式强依赖 Redis）。
- **更多引擎/平台问题**（swift 参数探测、torch 防降级、apex 残缺包、控制信号残留等）：见 `deploy/notebook/README.md`「常见问题」，两环境通用。

## 六、与 Notebook 环境的差异速查

| 项目 | ModelScope Notebook | Ubuntu 24.04 服务器 |
|---|---|---|
| Python 环境 | 系统 Python（镜像预装 torch 2.10.0） | 独立 venv `backend/.venv` |
| 依赖服务 | apt + 手动拉起（无 systemd） | apt + systemd（开机自启） |
| 前端托管 | FastAPI 单端口 8000 | FastAPI 8000 / Nginx 80 |
| 长期运行 | Notebook 会话易断，需 `--background` | systemd 常驻（推荐） |
| 数据持久 | 实例释放即丢，必须备份 | 磁盘持久，仍建议定期备份 |
| 初始化脚本 | `deploy/notebook/init_env.sh` | `deploy/ubuntu/init_env.sh` |
| 启动脚本 | `deploy/notebook/start.sh` | `deploy/ubuntu/start.sh` |
