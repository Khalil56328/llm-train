"""训练 / 推理 / 评测任务执行器

支持两种执行模式（settings.TRAIN_EXECUTION_MODE）：
- mock: 本地模拟执行，用于无 GPU / 无 swift 命令的环境下验证完整链路
- real: 真实执行 swift / vllm 命令（需 GPU 与 swift 环境）
- auto: 自动检测，存在 swift 命令则 real，否则 mock

Celery worker 与 API 本地调度共用本模块，保证执行逻辑一致。
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.engine.swift.adapter import SwiftEngineAdapter
from app.models.dataset import Dataset
from app.models.deployment import Deployment, DeployInstance
from app.models.evaluation import EvaluationTask
from app.models.model import Model, ModelVersion
from app.models.operator import OperatorVersion
from app.models.task import TrainTask
from app.models.task_log import TrainTaskLog, TrainTaskMetric
from app.tasks.control import clear_control, get_control


def _new_id() -> str:
    return uuid.uuid4().hex


def storage_dir() -> Path:
    """本地存储根目录（模型产物 / 评测报告 / 上传文件）"""
    base = Path(getattr(settings, "LOCAL_STORAGE_DIR", "storage"))
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent.parent / base
    return base


def _gpu_available() -> bool:
    """探测宿主机是否有可用 NVIDIA GPU（nvidia-smi 存在且能出结果）。

    auto 模式下作为 real 的额外前置条件：即便 swift 命令已安装，
    无 GPU 的机器（纯 CPU 服务器 / 未装驱动的实例）也应走 mock，
    避免真实训练/推理（vLLM 无 CUDA 直接崩）在无 GPU 环境反复失败。
    """
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        proc = subprocess.run(
            ["nvidia-smi", "-L"], capture_output=True, text=True, timeout=10,
        )
        return proc.returncode == 0 and bool((proc.stdout or "").strip())
    except Exception:  # noqa: BLE001
        return False


def exec_mode() -> str:
    """返回当前执行模式：real / mock

    - auto: 同时满足「已安装 swift 命令」且「存在可用 NVIDIA GPU」才走 real，
      否则回退 mock（无 GPU / 未装驱动 / 未装引擎均安全降级）；
    - real: 强制真实执行（无 swift / 无 GPU 时命令本身会失败，由任务报错体现）；
    - mock: 强制模拟执行。
    """
    mode = getattr(settings, "TRAIN_EXECUTION_MODE", "auto").lower()
    if mode == "auto":
        return "real" if shutil.which("swift") and _gpu_available() else "mock"
    return "real" if mode == "real" else "mock"


async def resolve_operator_version(
    session,
    operator_id: str,
    operator_version: Optional[str] = None,
) -> Optional[OperatorVersion]:
    """解析任务所选算子版本

    优先按 operator_version（版本 ID）精确匹配；未指定或版本不存在时回退该算子最新版本。
    """
    if not operator_id:
        return None
    if operator_version:
        result = await session.execute(
            select(OperatorVersion).where(
                OperatorVersion.id == operator_version,
                OperatorVersion.operator_id == operator_id,
            )
        )
        ver = result.scalar_one_or_none()
        if ver:
            return ver
    result = await session.execute(
        select(OperatorVersion)
        .where(OperatorVersion.operator_id == operator_id)
        .order_by(OperatorVersion.created_at.desc())
    )
    return result.scalars().first()


def build_process_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """构造传给子进程的环境变量：继承当前环境 + 单卡演示最低标准默认项 + 用户自定义"""
    env = dict(os.environ)
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    # 单卡演示：固定 CUDA_VISIBLE_DEVICES=0（若未由外部指定）
    env.setdefault("CUDA_VISIBLE_DEVICES", "0")
    if extra:
        env.update({k: str(v) for k, v in extra.items() if v is not None})
    return env


# ---------------------------------------------------------------------------
# 日志 / 指标写入器
# ---------------------------------------------------------------------------

class TaskLogWriter:
    """任务日志/指标批量写入器，降低 DB 提交频率

    seq 在任务内单调递增，由本类应用侧生成，保证排序与 WS 增量推送稳定。
    """

    def __init__(self, session, task_id: str, flush_size: int = 20):
        self.session = session
        self.task_id = task_id
        self.flush_size = flush_size
        self._seq = 0
        self._logs: List[TrainTaskLog] = []

    async def log(self, message: str, level: str = "INFO") -> None:
        self._seq += 1
        self._logs.append(TrainTaskLog(
            id=_new_id(),
            seq=self._seq,
            task_id=self.task_id,
            time=datetime.now(),
            level=level.upper(),
            message=message,
        ))
        if len(self._logs) >= self.flush_size:
            await self.flush()

    async def flush(self) -> None:
        if self._logs:
            self.session.add_all(self._logs)
            self._logs.clear()
            await self.session.flush()

    async def metric(self, step: int, loss: Optional[float], lr: Optional[float]) -> None:
        self._seq += 1
        self.session.add(TrainTaskMetric(
            id=_new_id(), seq=self._seq, task_id=self.task_id,
            step=step, loss=loss, lr=lr,
        ))
        await self.session.flush()


async def _handle_control(task, writer, session) -> bool:
    """处理暂停/取消控制信号，返回 True 表示任务应停止。"""
    ctl = get_control(task.id)
    if ctl == "cancel":
        task.status = "stopped"
        task.finished_at = datetime.now()
        await writer.log("收到取消信号，任务已停止", level="WARN")
        await writer.flush()
        await session.commit()
        return True
    if ctl == "pause":
        task.status = "paused"
        await writer.log(f"收到暂停信号，进度停留在 {task.progress or 0}%", level="WARN")
        await writer.flush()
        await session.commit()
        while get_control(task.id) == "pause":
            await asyncio.sleep(1)
        if get_control(task.id) == "cancel":
            task.status = "stopped"
            task.finished_at = datetime.now()
            await writer.log("暂停期间收到取消信号，任务已停止", level="WARN")
            await writer.flush()
            await session.commit()
            return True
        task.status = "running"
        await writer.log("任务已恢复执行", level="INFO")
        await writer.flush()
        await session.commit()
    return False


# ---------------------------------------------------------------------------
# 训练
# ---------------------------------------------------------------------------

async def _run_mock_training(session, writer, task, hyper: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """模拟训练：生成日志/指标/进度，支持暂停/取消"""
    total_steps = int(hyper.get("maxSteps") or hyper.get("max_steps") or 100)
    total_steps = max(10, min(total_steps, 500))
    rng = random.Random((task.id or "").__hash__() % (2 ** 31))
    cur_loss = 3.0 + rng.random()
    base_lr = float(hyper.get("learning_rate") or 2e-5)
    await writer.log(f"模拟训练开始：共 {total_steps} 步", level="INFO")

    for step in range(1, total_steps + 1):
        if await _handle_control(task, writer, session):
            return False, "stopped"
        cur_loss = max(0.2, cur_loss - 0.015 + (rng.random() - 0.5) * 0.02)
        lr = base_lr * (1 - 0.7 * step / total_steps)
        progress = int(step / total_steps * 100)
        if step % 2 == 0 or step == total_steps:
            await writer.log(
                f"[step {step}/{total_steps}] loss={cur_loss:.4f} lr={lr:.2e} progress={progress}%"
            )
            await writer.metric(step, round(cur_loss, 6), round(lr, 10))
            task.progress = progress
            await session.commit()
        await asyncio.sleep(0.02)

    task.status = "succeeded"
    task.progress = 100
    task.finished_at = datetime.now()
    await writer.log("训练完成", level="INFO")
    await writer.flush()
    await session.commit()
    return True, None


async def _run_mock_export(session, writer, task, hyper: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """模拟模型压缩/导出：生成步骤日志，支持暂停/取消"""
    total_steps = 20
    rng = random.Random((task.id or "").__hash__() % (2 ** 31))
    await writer.log(f"模拟压缩/导出开始：共 {total_steps} 步", level="INFO")
    for step in range(1, total_steps + 1):
        if await _handle_control(task, writer, session):
            return False, "stopped"
        progress = int(step / total_steps * 100)
        await writer.log(
            f"[export step {step}/{total_steps}] 量化层 {step} 处理完成 progress={progress}%"
        )
        task.progress = progress
        if step % 5 == 0:
            await writer.metric(step, None, None)
            await session.commit()
        await asyncio.sleep(0.02)
    task.status = "succeeded"
    task.progress = 100
    task.finished_at = datetime.now()
    await writer.log("模型压缩/导出完成", level="INFO")
    await writer.flush()
    await session.commit()
    return True, None


async def _run_real_training(session, writer, task, cmd: List[str]) -> Tuple[bool, Optional[str]]:
    """真实执行 swift 训练命令，逐行解析日志/指标/进度"""
    await writer.log("真实模式：使用 swift 命令执行训练", level="INFO")
    proc_env = build_process_env(task.env_vars or {})
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=settings.TRAIN_WORKSPACE or None,
            env=proc_env,
        )
    except FileNotFoundError:
        await writer.log("swift 命令不存在，请安装 MS-Swift 或改用 mock 模式", level="ERROR")
        await writer.flush()
        await session.commit()
        return False, "swift command not found"

    total_steps: Optional[int] = None
    total_pat = re.compile(r"total_steps['\"]?\s*[:=]\s*(\d+)", re.IGNORECASE)
    step_pat = re.compile(r"(?:^|[\s,{'\"]+)step['\"]?\s*[:=]\s*(\d+)", re.IGNORECASE)
    line_count = 0

    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        if not line.strip():
            continue
        # 控制信号（真实模式下暂停仅标记状态，取消则终止进程）
        ctl = get_control(task.id)
        if ctl == "cancel":
            proc.terminate()
            task.status = "stopped"
            task.finished_at = datetime.now()
            await writer.log("收到取消信号，终止训练进程", level="WARN")
            await writer.flush()
            await session.commit()
            return False, "stopped"
        if ctl == "pause":
            task.status = "paused"
            await writer.log("收到暂停信号，挂起训练进程", level="WARN")
            await writer.flush()
            await session.commit()
            _suspend_proc(proc)
            # 阻塞等待恢复信号（期间若收到取消则终止）
            while get_control(task.id) == "pause":
                await asyncio.sleep(1)
            if get_control(task.id) == "cancel":
                proc.terminate()
                task.status = "stopped"
                task.finished_at = datetime.now()
                await writer.log("暂停期间收到取消信号，终止训练进程", level="WARN")
                await writer.flush()
                await session.commit()
                return False, "stopped"
            _resume_proc(proc)
            clear_control(task.id)
            task.status = "running"
            await writer.log("任务已恢复执行", level="INFO")
            await writer.flush()
            await session.commit()
        # 解析 total_steps / step
        if total_steps is None:
            m = total_pat.search(line)
            if m:
                total_steps = int(m.group(1))
        loss = SwiftEngineAdapter.parse_loss_from_log(line)
        lr = SwiftEngineAdapter.parse_lr_from_log(line)
        m = step_pat.search(line)
        step = int(m.group(1)) if m else None
        await writer.log(line)
        if loss is not None or lr is not None:
            await writer.metric(step or 0, loss, lr)
        if step and total_steps and total_steps > 0:
            progress = max(0, min(99, int(step / total_steps * 100)))
            if progress != task.progress:
                task.progress = progress
        line_count += 1
        if line_count % 20 == 0:
            await writer.flush()
            await session.commit()

    rc = await proc.wait()
    await writer.flush()
    if rc != 0:
        await writer.log(f"训练进程退出码: {rc}", level="ERROR")
        await session.commit()
        return False, f"exit code {rc}"
    task.status = "succeeded"
    task.progress = 100
    task.finished_at = datetime.now()
    await writer.log("训练完成", level="INFO")
    await writer.flush()
    await session.commit()
    return True, None


async def _wait_inference_ready(dep, deploy_id: str, port: int) -> None:
    """真实模式下轮询探测推理服务就绪，避免服务未加载完就被判定为可访问"""
    import socket

    timeout = int(getattr(settings, "INFERENCE_READY_TIMEOUT", 180) or 180)
    append_deploy_log(deploy_id, f"等待推理服务就绪（最多 {timeout}s）...")
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        # 探测 TCP 端口是否可连接
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            append_deploy_log(deploy_id, "推理服务端口已就绪")
            dep.progress = 100
            return
        except OSError:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
        await asyncio.sleep(2)
    append_deploy_log(deploy_id, "推理服务就绪超时")
    dep.status = "failed"
    dep.error_message = f"推理服务在 {timeout}s 内未就绪"


def _suspend_proc(proc) -> None:
    """挂起子进程（真实暂停）。Unix 用 SIGSTOP，Windows 不支持则仅提示。"""
    import signal
    if hasattr(proc, "send_signal") and os.name != "nt":
        try:
            proc.send_signal(signal.SIGSTOP)
            return
        except Exception:
            pass
    if os.name == "nt":
        # Windows 下无 POSIX 信号，训练进程会继续，但状态已标记 paused，UI 会提示
        pass


def _resume_proc(proc) -> None:
    """恢复子进程。Unix 用 SIGCONT。"""
    import signal
    if hasattr(proc, "send_signal") and os.name != "nt":
        try:
            proc.send_signal(signal.SIGCONT)
        except Exception:
            pass


async def _create_output_model(session, task: TrainTask, output_dir: str) -> str:
    """训练成功后创建产出模型记录（含默认版本与落盘标识文件）"""
    mid = _new_id()
    out_path = Path(output_dir)
    try:
        out_path.mkdir(parents=True, exist_ok=True)
        # 确保产物目录非空：仅当目录中还没有真实 config.json 时才写标识文件，
        # 避免覆盖真实训练/量化产物的 config.json（否则产物模型因缺 model_type/
        # architectures 等字段而无法被部署加载）。
        cfg_path = out_path / "config.json"
        if not cfg_path.exists() or cfg_path.stat().st_size == 0:
            cfg_path.write_text(
                json.dumps({
                    "name": f"{task.name}-output",
                    "task_id": task.id,
                    "mock": exec_mode() == "mock",
                    "created_at": datetime.now().isoformat(),
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    except OSError:
        pass
    session.add(Model(
        id=mid,
        name=f"{task.name}-output",
        type="dialogue",
        spec="below-10b",
        version="v1",
        description=f"由训练任务「{task.name}」产出",
        storage_path=str(out_path),
        owner_id=task.created_by or "system",
        status="active",
    ))
    await session.flush()
    # 默认版本记录，与 model_service.import_model 结构保持一致
    session.add(ModelVersion(
        id=_new_id(),
        model_id=mid,
        version="v1",
        description=f"训练产物默认版本",
        storage_path=str(out_path),
        framework="swift",
        size=0,
        file_count=1,
        status="ready",
        is_default=True,
    ))
    await session.flush()
    return mid


async def run_training(task_id: str) -> str:
    """执行训练任务（Celery 与本地调度共用入口）"""
    async with AsyncSessionLocal() as session:
        writer = TaskLogWriter(session, task_id)
        task = None
        try:
            result = await session.execute(
                select(TrainTask).where(TrainTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                return "task_not_found"

            # 清空历史控制信号：cancel/pause 只对"设置它的那一次执行"有效，
            # 否则上一次遗留的 cancel（Redis 中 24h TTL）会让重新提交的任务
            # 一启动就被立即终止（表现为"收到取消信号，终止训练进程"）。
            clear_control(task_id)

            hyper = dict(task.hyper_params or {})
            env = task.env_vars or {}
            # ---- 算子生效：解析算子版本 → 参数契约（默认值/必填/取值）+ 命令模板 ----
            operator_name = None
            operator_base_image = None
            command_template = None
            if task.operator_id:
                ver = await resolve_operator_version(session, task.operator_id, task.operator_version)
                if ver:
                    operator_name = ver.name
                    operator_base_image = ver.base_image
                    command_template = ver.start_cmd or None
                    hyper, op_err = SwiftEngineAdapter.resolve_hyper_params(hyper, ver.start_params)
                    if op_err:
                        task.status = "failed"
                        task.error_message = op_err
                        task.finished_at = datetime.now()
                        await session.flush()
                        await session.commit()
                        await writer.log(f"算子参数校验失败：{op_err}", level="ERROR")
                        return "operator_param_error"
                else:
                    await writer.log(
                        f"算子版本未找到（operator_id={task.operator_id}, version={task.operator_version or '-'}），按平台默认方式执行",
                        level="WARN",
                    )
            # 基座模型路径优先使用模型 storage_path（与数据集对称），否则回退显示名
            # 演示版默认模型为 0.5B 级（Qwen/Qwen2.5-0.5B-Instruct，部署脚本自动下载录入）
            base_model = task.base_model_name or "Qwen/Qwen2.5-0.5B-Instruct"
            if task.base_model_id:
                mr = await session.execute(select(Model).where(Model.id == task.base_model_id))
                m = mr.scalar_one_or_none()
                if m and m.storage_path:
                    base_model = m.storage_path
            dataset_ref = task.dataset_id or ""
            if task.dataset_id:
                dr = await session.execute(select(Dataset).where(Dataset.id == task.dataset_id))
                ds = dr.scalar_one_or_none()
                if ds and ds.storage_path:
                    dataset_ref = ds.storage_path

            output_dir = str(storage_dir() / "models" / task_id)
            is_export = task.task_type == "compression"
            # 训练方式显式判断：优先取 hyper.training_method，其次从 sub_type 推导
            is_lora = (
                (hyper.get("training_method") or "").lower() == "lora"
                or (task.sub_type or "").lower().find("lora") >= 0
            )
            # LoRA 微调：补充 tuner_type + lora 目标模块，否则 swift 不会启用 LoRA
            if not is_export and is_lora:
                hyper.setdefault("tuner_type", "lora")
                hyper.setdefault("lora_target_modules", "all-linear")
            if is_export:
                # 压缩任务：演示版仅支持量化（swift export）；剪枝/蒸馏仅入库回显，不参与命令
                quant_method = str(hyper.get("quant_method") or hyper.get("quantMethod") or "bnb").lower()
                params = {k: v for k, v in hyper.items() if k not in ("quant_method", "quantMethod")}
                # 校准数据集：按任务所选校准数据集解析真实路径（GPTQ/AWQ 量化必须）。
                # 前端 hyperParams.calib_dataset 是级联选择值/ID 字符串，不能直接传给 swift，
                # 统一剥离后用 calibDatasetId 解析出的真实 storage_path 覆盖。
                params.pop("calib_dataset", None)
                calib_path = None
                if task.calib_dataset_id:
                    cr = await session.execute(select(Dataset).where(Dataset.id == task.calib_dataset_id))
                    cds = cr.scalar_one_or_none()
                    if cds and cds.storage_path:
                        calib_path = cds.storage_path
                if calib_path:
                    params["calib_dataset"] = calib_path
                # 量化位数校验：仅允许合法整数值，避免 swift export 报 invalid int
                qb = params.get("quant_bits")
                if qb is not None:
                    try:
                        qb_int = int(qb)
                    except (TypeError, ValueError):
                        task.status = "failed"
                        task.error_message = f"量化位数取值非法: {qb}（仅支持 1/2/3/4/8）"
                        task.finished_at = datetime.now()
                        await writer.log(f"训练失败: {task.error_message}", level="ERROR")
                        await writer.flush()
                        await session.commit()
                        return "quant_bits_invalid"
                    if qb_int not in (1, 2, 3, 4, 8):
                        task.status = "failed"
                        task.error_message = f"量化位数取值非法: {qb_int}（仅支持 1/2/3/4/8）"
                        task.finished_at = datetime.now()
                        await writer.log(f"训练失败: {task.error_message}", level="ERROR")
                        await writer.flush()
                        await session.commit()
                        return "quant_bits_invalid"
                    params["quant_bits"] = qb_int
                if quant_method in ("gptq", "awq") and not calib_path:
                    task.status = "failed"
                    task.error_message = (
                        f"量化方法 {quant_method.upper()} 需要校准数据集，"
                        "请在压缩任务中选择校准数据集后重试（或改用 bnb 量化，无需校准数据）"
                    )
                    task.finished_at = datetime.now()
                    await writer.log(f"训练失败: {task.error_message}", level="ERROR")
                    await writer.flush()
                    await session.commit()
                    return "quant_calib_missing"
                cmd = SwiftEngineAdapter.build_export_command(
                    model_path=base_model,
                    quant_method=quant_method,
                    output_dir=output_dir,
                    params=params,
                )
            else:
                cmd = SwiftEngineAdapter.build_train_command(
                    task_type=task.task_type,
                    sub_type=task.sub_type,
                    base_model=base_model,
                    dataset=dataset_ref,
                    output_dir=output_dir,
                    hyper_params=hyper,
                    env_vars=env,
                    command_template=command_template,
                )
            task.engine_command = " ".join(cmd)
            task.status = "running"
            task.progress = 5
            task.started_at = datetime.now()
            task.finished_at = None
            await session.flush()
            await session.commit()

            await writer.log(f"任务「{task.name}」开始执行", level="INFO")
            await writer.log(f"任务类型: {task.task_type}（{task.sub_type or '默认'}）", level="INFO")
            if operator_name:
                await writer.log(f"算子: {operator_name}（基础镜像: {operator_base_image or '未配置'}）", level="INFO")
            await writer.log(f"基座模型: {base_model}", level="INFO")
            await writer.log(f"执行模式: {exec_mode().upper()}", level="INFO")
            await writer.log(f"执行命令: {' '.join(cmd)}", level="INFO")
            if task.task_type == "alignment":
                await writer.log(
                    "提示：偏好对齐（DPO/KTO/ORPO/SimPO）要求数据集为偏好对格式"
                    "（chosen/rejected，可用演示数据集 preference_demo）；若解析失败请核对数据集格式",
                    level="INFO",
                )

            # ---- 真实模式前置检查：模型/数据集路径必须真实存在 ----
            # 若记录的 storage_path 指向磁盘上不存在的目录（未下载 / 未配置），
            # 直接交给 swift 会在 set_model_type 等内部步骤抛晦涩的 traceback；
            # 这里在启动前给出明确错误，并提示两条出路（准备真实数据 / 切 mock）。
            if exec_mode() == "real" and not is_export:
                missing = []

                def _looks_like_hub_id(p: str) -> bool:
                    """形如 org/model 的两段式字符串视为 ModelScope/HF hub id，跳过本地校验"""
                    segs = p.split("/")
                    return (
                        len(segs) == 2
                        and all(seg for seg in segs)
                        and not p.startswith(("/", ".", "\\"))
                    )

                for label, p in (("模型", base_model), ("数据集", dataset_ref)):
                    if not p:
                        missing.append(f"{label}路径为空（记录未配置 storage_path）")
                    elif not _looks_like_hub_id(p) and not os.path.exists(p):
                        missing.append(f"{label}路径不存在: {p}")
                if missing:
                    detail = "；".join(missing)
                    task.status = "failed"
                    task.error_message = (
                        f"真实训练前置检查未通过：{detail}。"
                        "请下载真实模型并准备真实数据集、更新对应 storage_path 后重试，"
                        "或设置 TRAIN_EXECUTION_MODE=mock 走模拟执行"
                    )
                    task.finished_at = datetime.now()
                    await writer.log(f"训练失败: {task.error_message}", level="ERROR")
                    await writer.flush()
                    await session.commit()
                    return "preflight_failed"

            if is_export:
                # 导出路径：real 复用子进程执行器，mock 复用模拟执行器
                ok, err = await _run_real_training(session, writer, task, cmd) if exec_mode() == "real" \
                    else await _run_mock_export(session, writer, task, hyper)
            elif exec_mode() == "real":
                ok, err = await _run_real_training(session, writer, task, cmd)
            else:
                ok, err = await _run_mock_training(session, writer, task, hyper)

            if ok:
                out_model_id = await _create_output_model(session, task, output_dir)
                task.output_model_id = out_model_id
                task.output_model_name = f"{task.name}-output"
                task.status = "succeeded"
                task.progress = 100
                task.finished_at = datetime.now()
                await writer.log(f"产出模型已入库: {task.output_model_name}", level="INFO")
                await writer.flush()
                await session.commit()
            elif err != "stopped":
                task.status = "failed"
                task.error_message = err or "unknown error"
                task.finished_at = datetime.now()
                await writer.log(f"训练失败: {task.error_message}", level="ERROR")
                await writer.flush()
                await session.commit()

            clear_control(task_id)
            return "ok"
        except Exception as exc:  # noqa: BLE001
            try:
                if task is not None:
                    task.status = "failed"
                    task.error_message = str(exc)[:2000]
                    task.finished_at = datetime.now()
                await writer.log(f"训练异常: {exc}", level="ERROR")
                await writer.flush()
                await session.commit()
            except Exception:
                await session.rollback()
            clear_control(task_id)
            return "error"


# ---------------------------------------------------------------------------
# 推理（部署）
# ---------------------------------------------------------------------------

# 已启动的 mock 推理服务句柄：deploy_id -> server
_MOCK_INFERENCE_SERVERS: Dict[str, "_MockInferenceServer"] = {}
# 真实模式推理进程句柄：deploy_id -> Popen
_REAL_INFERENCE_PROCS: Dict[str, Any] = {}


class _MockInferenceServer:
    """内存版 OpenAI 兼容推理服务，用于 mock 模式下让"部署→访问"真正可用。

    仅在 127.0.0.1 上监听，实现 /v1/models 与 /v1/chat/completions，
    从请求 messages 拼接出模拟回复，保证 test_deployment 能真实连通。
    """

    def __init__(self, host: str, port: int, model_name: str, deploy_id: str = ""):
        self.host = host
        self.port = port
        self.model_name = model_name or "mock-model"
        self.deploy_id = deploy_id
        self._server: Any = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        owner = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # 静默
                pass

            def _send_json(self, obj, code=200):
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    self._send_json({
                        "object": "list",
                        "data": [{"id": owner.model_name, "object": "model", "owned_by": "mock"}],
                    })
                else:
                    self._send_json({"error": "not found"}, 404)

            def do_POST(self):
                if not self.path.rstrip("/").endswith("/chat/completions"):
                    self._send_json({"error": "not found"}, 404)
                    return
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    data = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    data = {}
                messages = data.get("messages") or []
                text = " ".join(
                    str(m.get("content", "")) for m in messages if isinstance(m, dict)
                ).strip() or "（空输入）"
                if owner.deploy_id:
                    append_deploy_log(owner.deploy_id, f"[推理请求] messages={len(messages)}, input={text[:80]}")
                reply = (
                    f"[mock 推理服务] 收到 {len(messages)} 条消息。"
                    f"模型：{owner.model_name}。你的输入是：{text[:100]}"
                )
                self._send_json({
                    "id": f"mock-{uuid.uuid4().hex[:12]}",
                    "object": "chat.completion",
                    "model": owner.model_name,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": len(text), "completion_tokens": len(reply), "total_tokens": len(text) + len(reply)},
                })

        try:
            self._server = ThreadingHTTPServer((self.host, self.port), _Handler)
        except OSError:
            return False
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass


def deploy_log_path(deploy_id: str) -> Path:
    """部署日志文件路径（storage/logs/deploy/{id}.log）"""
    d = storage_dir() / "logs" / "deploy"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{deploy_id}.log"


def append_deploy_log(deploy_id: str, line: str) -> None:
    try:
        with open(deploy_log_path(deploy_id), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} | {line}\n")
    except OSError:
        pass


async def stop_inference_service(deploy_id: str) -> str:
    """停止推理服务：关闭 mock 内存服务 / 真实推理进程，并回填 POD 实例状态为 stopped"""
    server = _MOCK_INFERENCE_SERVERS.pop(deploy_id, None)
    if server is not None:
        server.stop()
    proc = _REAL_INFERENCE_PROCS.pop(deploy_id, None)
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        except Exception:
            pass
    append_deploy_log(deploy_id, "推理服务已停止")
    async with AsyncSessionLocal() as session:
        try:
            inst_result = await session.execute(
                select(DeployInstance).where(DeployInstance.deploy_id == deploy_id)
            )
            for inst in inst_result.scalars().all():
                inst.status = "stopped"
            await session.commit()
        except Exception:
            await session.rollback()
    return "ok"


async def run_inference(deploy_id: str) -> str:
    """启动推理服务（Celery 与本地调度共用入口）"""
    async with AsyncSessionLocal() as session:
        dep = None
        try:
            result = await session.execute(
                select(Deployment).where(Deployment.id == deploy_id)
            )
            dep = result.scalar_one_or_none()
            if not dep:
                return "deployment_not_found"

            model_path = dep.model_name or "Qwen/Qwen2.5-0.5B-Instruct"
            if dep.model_id:
                mr = await session.execute(select(Model).where(Model.id == dep.model_id))
                m = mr.scalar_one_or_none()
                if m and m.storage_path:
                    model_path = m.storage_path

            port = dep.access_port or dep.container_port or 8000
            cmd = SwiftEngineAdapter.build_inference_command(
                model_path=model_path,
                framework=dep.inference_framework or "vLLM",
                port=port,
                params=dep.params or {},
            )
            dep.engine_command = " ".join(cmd)
            dep.status = "running"
            dep.progress = 60
            dep.endpoint = f"http://0.0.0.0:{port}/v1"
            dep.error_message = None
            await session.flush()
            await session.commit()

            if exec_mode() == "real":
                # 真实模式：后台常驻进程（容器/GPU 环境由外部编排），日志写入文件（方案7）
                append_deploy_log(deploy_id, f"启动推理服务: {' '.join(cmd)}")
                try:
                    log_f = open(deploy_log_path(deploy_id), "a", encoding="utf-8")
                    p = subprocess.Popen(
                        cmd,
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        cwd=settings.TRAIN_WORKSPACE or None,
                        env=build_process_env(),
                    )
                    _REAL_INFERENCE_PROCS[deploy_id] = p
                except Exception as exc:  # noqa: BLE001
                    dep.status = "failed"
                    dep.error_message = f"启动进程失败: {exc}"
                    await session.commit()
                    return "error"
                # 等待服务就绪（vLLM 加载模型需要时间）
                await _wait_inference_ready(dep, deploy_id, port)
                if dep.status == "failed":
                    await session.commit()
                    return "error"
                # 若进程过早退出，标记失败
                if p.poll() is not None and p.returncode != 0:
                    dep.status = "failed"
                    dep.progress = 0
                    dep.error_message = f"推理服务进程已退出（exit={p.returncode}），详见部署日志"
                    append_deploy_log(deploy_id, f"推理进程退出 exit={p.returncode}")
                    await session.commit()
                    return "error"
            else:
                # mock 模式：启动内存推理服务，让在线访问真正可用
                append_deploy_log(deploy_id, f"启动 mock 推理服务（mock 模式）")
                server = _MockInferenceServer("127.0.0.1", port, dep.model_name or "mock-model", deploy_id)
                if server.start():
                    _MOCK_INFERENCE_SERVERS[deploy_id] = server
                    dep.endpoint = f"http://127.0.0.1:{port}/v1"
                    append_deploy_log(deploy_id, f"mock 推理服务监听 http://127.0.0.1:{port}/v1")
                else:
                    dep.status = "failed"
                    dep.error_message = f"mock 推理服务启动失败（端口 {port} 可能被占用）"
                    await session.commit()
                    return "error"

            dep.status = "running"
            dep.progress = 100
            # endpoint 统一用 127.0.0.1 供后端代理访问；对外暴露由容器/Nginx 编排
            dep.endpoint = f"http://127.0.0.1:{port}/v1"
            await session.flush()

            # 回填 POD 实例状态（P1-4 修复）
            inst_result = await session.execute(
                select(DeployInstance).where(DeployInstance.deploy_id == deploy_id)
            )
            for inst in inst_result.scalars().all():
                inst.status = "running"
                inst.host_ip = "127.0.0.1"
                inst.pod_ip = "127.0.0.1"
            await session.commit()
            return "ok"
        except Exception as exc:  # noqa: BLE001
            try:
                if dep is not None:
                    dep.status = "failed"
                    dep.error_message = str(exc)[:2000]
                    await session.commit()
            except Exception:
                await session.rollback()
            return "error"


# ---------------------------------------------------------------------------
# 评测
# ---------------------------------------------------------------------------

SCENE_NAMES = {
    "code": "代码生成",
    "alignment": "对齐能力",
    "agent": "智能体",
    "safety": "安全对齐",
    "reasoning": "逻辑推理",
    "general": "通用能力",
    "knowledge": "知识问答",
    "math": "数学推理",
}


def _evaluation_dims(scenes: Any) -> List[str]:
    """将评测场景映射为中文维度名"""
    if isinstance(scenes, list) and scenes:
        return [SCENE_NAMES.get(str(s), str(s)) for s in scenes]
    return ["代码生成", "逻辑推理", "安全对齐"]


async def run_evaluation(eval_id: str) -> str:
    """执行评测任务并生成报告文件（Celery 与本地调度共用入口）"""
    async with AsyncSessionLocal() as session:
        e = None
        try:
            result = await session.execute(
                select(EvaluationTask).where(EvaluationTask.id == eval_id)
            )
            e = result.scalar_one_or_none()
            if not e:
                return "evaluation_not_found"

            e.status = "running"
            e.progress = 10
            e.error_message = None
            await session.flush()
            await session.commit()

            dims = _evaluation_dims(e.scenes)
            rng = random.Random((e.id or eval_id).__hash__() % (2 ** 31))
            dim_scores = [
                {"dimension": dim, "score": round(60 + rng.random() * 38, 2)}
                for dim in dims
            ]
            overall = round(sum(s["score"] for s in dim_scores) / len(dim_scores), 2) if dim_scores else 0.0

            # 黄金标准答案对比样例（真实评测中由数据集参考答案与模型输出比对生成）
            samples = [
                {
                    "question": f"{dim}评测样本 #{i + 1}",
                    "answer": f"模型输出（基于{dim}场景生成的结果，用于与标准答案对比）",
                    "golden": f"黄金标准答案（{dim}场景预期结果）",
                    "matched": rng.random() > 0.2,
                    "score": round(60 + rng.random() * 40, 2),
                }
                for i, dim in enumerate(dims)
            ]

            report = {
                "evalId": e.id,
                "name": e.name,
                "score": overall,
                "dimensionScores": dim_scores,
                "samples": samples,
                "summary": f"本次评测覆盖 {len(dims)} 个维度，综合得分 {overall} 分。",
                "generatedAt": datetime.now().isoformat(),
            }
            report_dir = storage_dir() / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / f"{e.id}.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

            e.status = "completed"
            e.progress = 100
            e.score = overall
            e.report_url = f"/static/reports/{e.id}.json"
            e.finished_at = datetime.now()
            await session.flush()
            await session.commit()
            return "ok"
        except Exception as exc:  # noqa: BLE001
            try:
                if e is not None:
                    e.status = "failed"
                    e.error_message = str(exc)[:2000]
                    e.finished_at = datetime.now()
                    await session.commit()
            except Exception:
                await session.rollback()
            return "error"
