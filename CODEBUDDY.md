# CODEBUDDY.md This file provides guidance to CodeBuddy when working with code in this repository.

## Common Commands

### Frontend (`model_train/web-ui/`)

```bash
npm install                         # Install dependencies
npm run dev                         # Start dev server on port 5173 (hot-reload)
npm run build                       # Type-check (vue-tsc) then production build to dist/
npm run preview                     # Preview production build locally
npm run lint                        # ESLint --fix on .vue/.ts/.tsx files in src/
npm run format                      # Prettier format on src/**/*.{vue,ts,tsx,scss,json}
```

Dev server proxies `/api` to `http://localhost:8000`. The build uses `vue-tsc --noEmit` for type checking before Vite builds. Production output is served via Nginx (see `nginx.conf`).

### Backend (`model_train/backend/`)

```bash
pip install -r requirements.txt     # Install Python dependencies (Python 3.10+)
python main.py                      # Start FastAPI dev server on port 8000 (hot-reload)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload  # Alternative start command
python test_import.py               # Verify all module imports work
pytest tests/ -v                    # Run tests (test suite not yet populated)
pytest tests/ -v -k test_name       # Run a single test by name pattern
```

The backend requires MySQL, Redis, and MinIO services to be running (see `.env`). Set `DEBUG=true` in `.env` for development.

### Docker（仅开发/CI 参考，标准部署不使用容器）

> **标准部署不使用 Docker**：整个项目（前端 + API + Worker）前后端一体直接运行在 GPU 宿主机上
> （见 `deploy/notebook/README.md` 路径 A、`deploy/ubuntu/README.md` 路径 C），MySQL/Redis 由 apt 安装，
> 前端由 FastAPI 直接托管。真实训练/推理（MS-Swift + vLLM）由 executor 以 subprocess 调用宿主机
> swift/vllm，容器内无 GPU 无法真实执行。以下镜像仅保留供开发/CI 或历史参考：

```bash
# API service（仅开发/CI）
docker build -t llm-train-api -f model_train/backend/Dockerfile model_train/backend/
docker run -p 8000:8000 llm-train-api

# Training worker（仅开发/CI；GPU 训练请直接在 GPU 宿主机装引擎后跑）
docker build -t llm-train-worker -f model_train/backend/Dockerfile.worker model_train/backend/
docker run --gpus all llm-train-worker

# Frontend with Nginx（仅开发/CI；标准部署由 FastAPI 托管 dist）
docker build -t llm-train-web -f model_train/web-ui/Dockerfile model_train/web-ui/
docker run -p 80:80 llm-train-web
```

## Architecture Overview

This is **LLM Training & Inference Platform** — a full-stack MLOps platform for large language model fine-tuning, alignment, compression, deployment, and evaluation. It uses **MS-Swift** as the underlying training/inference engine, wrapped by a custom **Vue 3 + FastAPI** platform.

### High-Level Architecture

```
Vue 3 SPA (Element Plus)  →  REST API / WebSocket  →  FastAPI (Python)
                                                            │
                              ┌─────────────────────────────┼─────────────────────────────┐
                              ▼                             ▼                             ▼
                         MySQL (asyncmy)              Redis (Celery)              MinIO (object storage)
                              │                             │                             │
                              ▼                             ▼                             ▼
                    metadata & config             task queue & cache           models, datasets, operators
```

The platform models an end-to-end MLOps pipeline: **Operators → Datasets → Training → Models → Deployment → Evaluation**.

### Backend Architecture (`model_train/backend/`)

The backend follows a standard **three-layer architecture**:

- **API layer** (`app/api/v1/`): 9 route modules (auth, operators, datasets, models, training, deployments, evaluations, dict, notifications), all mounted under `/api`. Uses FastAPI `Depends(get_db)` for database sessions and `Depends(get_current_user)` for JWT authentication on all endpoints except `/api/auth/login`.
- **Service layer** (`app/services/`): 9 service classes, one per business domain. Each service receives an `AsyncSession` in its constructor and operates on SQLAlchemy ORM models. Services handle CRUD, status management, statistics, and business logic. They return `Dict` or `Optional[Dict]`.
- **Model layer** (`app/models/`): 9 SQLAlchemy ORM models mapping to MySQL tables. Three entity groups (Operator, Dataset, Model) use a **main-table + version-table** pattern with UUID hex primary keys. `DeclarativeBase` defined in `app/core/database.py`.

**Core modules** (`app/core/`):
- `config.py`: Pydantic Settings loading from `.env` — MySQL DSN, Redis URL, JWT secrets, MinIO credentials, MS-Swift image config.
- `database.py`: Async SQLAlchemy engine with `asyncmy` driver, connection pool (size=10, overflow=20, recycle=3600s, pre-ping=True). Provides `get_db()` async generator for FastAPI dependency injection.
- `auth.py`: `SecurityService` class for bcrypt password hashing and JWT token creation/verification. `get_current_user` dependency extracts and validates the Bearer token, returns `{id, username, nickname, role}`.
- `response.py`: Standardized JSON response format — `{code: 0, message, data}` for success, `{code: 1, message, data: None}` for errors, plus paginated wrapper.

**Engine layer** (`app/engine/swift/adapter.py`): `SwiftEngineAdapter` is a static utility class that maps platform business parameters to MS-Swift CLI commands via `build_train_command()`, `build_inference_command()`, and `build_export_command()`. It handles task-type-to-subcommand mapping (sft/rlhf/pt/export), hyperparameter name translation, and log parsing for loss/lr extraction. This adapter is **not yet integrated** into the training pipeline (training endpoints currently only change task status in the database).

**Async tasks** (`app/tasks/worker.py`): Celery application with Redis broker/backend. Task execution (train/inference/eval) is implemented in `app/tasks/executor.py` and runs via `subprocess` on the GPU host (or in-process when no Redis worker is available); no separate worker container is used in standard deployment.

**Key entity relationships**:
- TrainTask references base_model_id (Model), operator_id (Operator), dataset_id (Dataset) → produces output_model_id (Model)
- Deployment references model_id (Model) + operator_id (Operator) → serves at endpoint
- EvaluationTask references dataset_id (Dataset) + deployment_id (Deployment) → produces score + report_url

**Startup flow** (`main.py` lifespan): Creates all DB tables → seeds admin user (admin/admin123, super_admin role) → seeds 11 enum dictionaries (task_status, dataset_data_type, model_type, inference_framework, etc.) → rollback seed data on failure without blocking startup.

**Current maturity**:
- DB models and services: Fully implemented with CRUD + statistics
- API routes: Fully wired, but some endpoints return mock data (training logs, metrics, deployment test results, eval reports)
- Schema layer: Only `operator.py` has full Pydantic schemas; other modules pass raw `dict` via `Body(...)`
- Engine integration: Adapter code exists but is not called from training endpoints
- Celery tasks: Stubs only (all `pass`)
- WebSocket (`app/ws/`): Empty directory, reserved for real-time log streaming
- Tests: Empty directory, only `test_import.py` for module import verification

### Frontend Architecture (`model_train/web-ui/`)

The frontend is a **Vue 3 SPA** with TypeScript, Vite, Element Plus, Pinia, Vue Router, Axios, and ECharts. Theme color is red (#e63946).

**Directory structure** follows Vue 3 conventions:
- `src/api/`: 5 API modules (`dataset.ts`, `model.ts`, `operator.ts`, `service.ts`, `training.ts`) — each wraps the corresponding backend REST endpoints using the shared Axios instance from `src/utils/request.ts`.
- `src/stores/index.ts`: 4 Pinia stores — `useUserStore` (auth + user info, persisted to localStorage), `useMenuStore` (dynamic sidebar menu from backend), `useDictStore` (enum dictionary lookup), `useNotificationStore` (notification badge + list).
- `src/router/index.ts`: Nested routing with `AppLayout` as parent. Public route `/login` has no layout. Six business modules (operator, data, train, model, service, ops) are loaded as async routes. Route guard checks `localStorage.access_token`.
- `src/components/common/`: Reusable components driven by configuration objects — `DataTable` (dynamic columns, pagination, expandable rows), `SearchFilter` (keyword + filter slots), `SectionForm` (grouped form field rendering by section), `CardGrid` (icon card display), `StepCards` (wizard step indicator), `KvEditor` (key-value pair editor), `PageHeaderCard` (page title with red gradient).
- `src/components/layout/`: `AppLayout` (sidebar + header + router-view), `AppSidebar` (collapsible menu), `AppHeader` (breadcrumbs + notifications + user dropdown).
- `src/views/`: 24 Vue pages organized by business module. The operator module (7 files) is the most complex with two-level entity management (operator + versions) and image configuration. Training module (7 files) supports 5 training types and a 4-step creation wizard. Service module (3 files) covers deployment management, evaluation, and report viewing.
- `src/types/index.ts`: Complete TypeScript type definitions for all business entities, including enum maps with display labels and colors.
- `src/utils/request.ts`: Axios wrapper with global loading counter, automatic Bearer token injection, unified response unwrapping (`data.data`), 401 redirect to login, and upload progress support.

**Custom directives** (`src/directives/index.ts`): `v-permission` (role-based DOM removal) and `v-click-outside` (click-outside detection).

**Styling**: SCSS with `variables.scss` defining theme colors, layout dimensions (sidebar 220px/64px, header 56px), and design tokens. `global.scss` overrides Element Plus CSS variables and provides utility classes. The SCSS `additionalData` config injects `variables.scss` globally into all component styles.

**Build & deploy**: Vite config uses `unplugin-auto-import` (auto-imports Vue, Router, Pinia APIs) and `unplugin-vue-components` (auto-registers Element Plus components with SCSS import). Production build splits chunks: `element-plus` and `vendor` (Vue/Router/Pinia/Axios). Standard deployment: `npm run build` → `web-ui/dist` 由后端 FastAPI 直接托管（`FRONTEND_DIST_DIR`，单端口 8000），无需独立前端服务。

### Infrastructure & Deployment

- **MySQL**: Metadata storage for all entities (connection: `mysql+asyncmy://`)
- **Redis**: Celery broker/backend + cache
- **MinIO**: Object storage for model files, datasets, and operator packages
- **GPU 训练/推理执行**: 由 executor（`app/tasks/executor.py`）以 `subprocess` 在 GPU 宿主机直接调用 MS-Swift/vLLM，任务经 Celery 派发（无 Redis worker 时降级为 API 进程内执行）；不使用独立 GPU 容器
- **Nginx**: Serves built frontend, proxies `/api/` to FastAPI backend, proxies `/ws/` for WebSocket

### Project Documentation

- `docs/大模型训推平台技术方案_Vue3.md`: Technical design document describing the MS-Swift engine integration, technology selection, and architecture decisions
- `docs/codebuddy/`: 8 sub-plans covering frontend, backend, infrastructure, and testing
- `docs/训推平台功能点.xlsx`: Feature checklist
- `plan/`: Additional planning documents
