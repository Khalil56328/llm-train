"""MS-Swift 引擎适配器 - 参数映射与命令生成"""
import json
import re
import shlex
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set


class SwiftEngineAdapter:
    """将业务层训练/推理参数转换为 MS-Swift CLI 命令"""

    # 任务类型 → Swift 子命令映射
    TASK_CMD_MAP = {
        "fine-tune": "swift sft",
        "alignment": "swift rlhf",
        "pretrain": "swift pt",
        "compression": "swift export",
        "scene": "swift sft",  # 场景训练本质为 SFT，场景特有参数通过 hyper_params 透传
    }

    # 偏好对齐子类型映射
    RLHF_TYPE_MAP = {
        "RLHF": "ppo",
        "PPO": "ppo",
        "DPO": "dpo",
        "KTO": "kto",
        "GRPO": "grpo",
        "GSPO": "gspo",
        "ORPO": "orpo",
        "SIMPO": "simpo",
    }

    # 平台内部字段：仅用于页面选择/入库回显或控制逻辑，不参与 swift 命令。
    # 演示模式下训练框架/训练方法等在命令生成时按任务类型定死，
    # 但页面选择的数据必须能入库并在详情页回显。
    PLATFORM_INTERNAL_KEYS = frozenset({
        "training_method",      # 页面"训练方法"选择（LoRA/全量），仅入库回显；LoRA 生效由 executor 按 sub_type 注入 tuner_type
        "framework",            # 页面"训练框架"选择（ms-swift），命令生成时定死 swift
        "method", "alignMethod",
        "compressionType",
        "sceneType", "stages", "globalEnvVars",
        "notifyOnFailure", "notifyOnSuccess",
    })

    # 压缩/导出任务中仅用于入库回显的展示字段（swift export 不识别，透传会导致 argparse 报错）。
    # 注意：quant_bits / group_size / calib_dataset / calib_samples 是 swift export 的合法参数，
    # 正常透传（calib_dataset 由 executor 按任务所选校准数据集解析为真实路径后传入）。
    EXPORT_INTERNAL_KEYS = frozenset(PLATFORM_INTERNAL_KEYS) | {
        "quant_method", "quantMethod",   # executor 已单独提取为 --quant_method
        "pruning_method", "pruning_ratio",  # 演示版不支持剪枝，仅入库回显
        "distill_temp", "distill_alpha",    # 演示版不支持蒸馏，仅入库回显
        "teacher_model", "epochs",          # 演示版不支持蒸馏，仅入库回显
    }

    # 参数名映射（前端 → Swift 参数名；最终以运行时 `swift <子命令> --help` 探测结果为准，
    # _resolve_flag 会按需把下划线转连字符、或映射到 2.x/3.x/4.x 的改名参数）
    PARAM_MAP = {
        "learning_rate": "--learning_rate",
        "epochs": "--num_train_epochs",
        "batch_size": "--per_device_train_batch_size",
        "max_length": "--max_length",
        "lora_rank": "--lora_rank",
        "lora_alpha": "--lora_alpha",
        "weight_decay": "--weight_decay",
        "warmup_ratio": "--warmup_ratio",
        "warmup_steps": "--warmup_steps",
        "logging_steps": "--logging_steps",
        "save_steps": "--save_steps",
        "eval_steps": "--eval_steps",
        "gradient_accumulation_steps": "--gradient_accumulation_steps",
        "tuner_type": "--tuner_type",               # 2.x 参数名；4.x 为 --train_type，_resolve_flag 自动适配
        "train_type": "--train_type",               # 3.x/4.x 参数名（lora / qlora / full）
        "lora_target_modules": "--lora_target_modules",  # 4.x 可能为 --target_modules，自动适配
        "target_modules": "--target_modules",
        "quant_bits": "--quant_bits",
        "group_size": "--group_size",
        "calib_dataset": "--calib_dataset",
        "calib_samples": "--calib_samples",
    }

    # 各子命令的 CLI 选项缓存（按子命令分别探测；pt/sft 等参数名可能不一致）
    _swift_opts_cache: Dict[str, Set[str]] = {}

    # swift 顶层子命令 / 版本探测缓存（swift --help / swift --version）
    _subcommands_cache: Optional[Set[str]] = None
    _swift_version_cache: Optional[str] = None
    # vLLM CLI 子命令缓存（vllm --help）
    _vllm_subcommands_cache: Optional[Set[str]] = None

    # 已知 swift 顶层子命令令牌（ms-swift 各版本 --help 布局差异大，做兜底扫描）
    _KNOWN_SUBCOMMANDS = (
        "sft", "rlhf", "pt", "export", "deploy", "eval", "infer", "train",
        "merge", "sample", "webui", "app", "resume", "post",
    )

    # 新版 ms-swift 若移除旧子命令时的替代候选（探测到缺失时依次尝试）。
    # ms-swift 3.x/4.x 大版本重构频繁：预训练/偏好对齐/部署子命令可能被合并
    # 或改名（如并入 swift train / swift sft / swift infer）。执行时会先探测
    # `swift --help` 实际存在的子命令，缺失时按以下候选兜底，再按探测结果执行。
    SUBCOMMAND_ALIASES: Dict[str, Tuple[str, ...]] = {
        "pt": ("train", "sft"),         # 4.x 若将预训练并入 swift train / sft
        "rlhf": ("sft", "train"),       # 4.x 若将偏好对齐并入 swift sft / train
        "deploy": ("infer", "deploy"),  # 4.x 若将部署改名为 swift infer
        # "export": ("train",),         # 导出/量化暂无可靠候选；缺失时保留默认并 WARN（报错信息可定位）
    }

    @staticmethod
    def _warn(msg: str) -> None:
        try:
            print(f"[SWIFT-ADAPTER][WARN] {msg}", file=sys.stderr, flush=True)
        except Exception:
            pass

    @classmethod
    def swift_version(cls) -> Optional[str]:
        """探测当前 swift 版本号（swift --version 输出中的 x.y.z），结果缓存。

        ms-swift 2.x/3.x/4.x 的 CLI 差异较大，业务层可据此做分支适配。
        探测失败（未安装 / 超时 / 无版本号）返回 None。
        """
        if cls._swift_version_cache is not None:
            return cls._swift_version_cache
        version: Optional[str] = None
        try:
            import subprocess
            proc = subprocess.run(
                ["swift", "--version"],
                capture_output=True, text=True, timeout=60,
            )
            text = (proc.stdout or "") + (proc.stderr or "")
            m = re.search(r"(\d+\.\d+\.\d+)", text)
            version = m.group(1) if m else None
        except Exception:
            pass
        cls._swift_version_cache = version
        return version

    @classmethod
    def _swift_subcommands(cls) -> Set[str]:
        """探测 swift CLI 顶层子命令（swift --help），结果缓存。

        ms-swift 大版本（3.x/4.x）重构频繁，子命令可能改名/移除；
        结果用于校验平台默认子命令是否仍存在，缺失时按 SUBCOMMAND_ALIASES 回退。
        探测失败（swift 未装 / 超时）返回空集，调用方按默认子命令处理。
        """
        if cls._subcommands_cache is not None:
            return cls._subcommands_cache
        cmds: Set[str] = set()
        try:
            import subprocess
            proc = subprocess.run(
                ["swift", "--help"],
                capture_output=True, text=True, timeout=60,
            )
            text = (proc.stdout or "") + (proc.stderr or "")
            # 顶层子命令行：形如 "  sft     微调"（缩进 2+ 空格 + 命令名）
            for line in text.splitlines():
                m = re.match(r"^\s{2,}([a-z][a-z0-9_-]*)\s", line)
                if m:
                    cmds.add(m.group(1))
            # 兜底：已知命令令牌出现在帮助文本中即视为存在
            for token in cls._KNOWN_SUBCOMMANDS:
                if re.search(rf"(?<![a-z0-9_-]){token}(?![a-z0-9_-])", text):
                    cmds.add(token)
        except Exception:
            pass
        cls._subcommands_cache = cmds
        return cmds

    @classmethod
    def _vllm_subcommands(cls) -> Set[str]:
        """探测 vLLM CLI 顶层子命令（vllm --help），结果缓存。

        vLLM >=0.6 官方推荐入口为 `vllm serve`，旧入口
        `python -m vllm.entrypoints.openai.api_server` 已弃用（未来版本可能移除）。
        探测失败（vllm 未装 / 超时）返回空集，调用方回退旧入口。
        """
        if cls._vllm_subcommands_cache is not None:
            return cls._vllm_subcommands_cache
        cmds: Set[str] = set()
        try:
            import subprocess
            proc = subprocess.run(
                ["vllm", "--help"],
                capture_output=True, text=True, timeout=60,
            )
            text = (proc.stdout or "") + (proc.stderr or "")
            for line in text.splitlines():
                m = re.match(r"^\s{2,}([a-z][a-z0-9_-]*)\s", line)
                if m:
                    cmds.add(m.group(1))
            if re.search(r"(?<![a-z0-9_-])serve(?![a-z0-9_-])", text):
                cmds.add("serve")
        except Exception:
            pass
        cls._vllm_subcommands_cache = cmds
        return cmds

    @classmethod
    def _resolve_subcommand(cls, default_cmd: str) -> str:
        """把平台默认 swift 子命令（如 'swift rlhf'）解析为当前安装版本真实存在的子命令。

        - 探测到且默认子命令存在：原样返回；
        - 默认子命令缺失：按 SUBCOMMAND_ALIASES 依次尝试替代候选；
        - 替代候选也不存在 / 探测失败：保留默认并输出 WARN（实际执行会给出明确报错）。
        """
        cmd_name = default_cmd.split()[-1]
        available = cls._swift_subcommands()
        if not available or cmd_name in available:
            return default_cmd
        for cand in cls.SUBCOMMAND_ALIASES.get(cmd_name, ()):
            if cand in available:
                cls._warn(
                    f"swift 子命令 '{cmd_name}' 在当前版本不存在"
                    f"（可用: {sorted(available)}），已改用替代命令 '{cand}'"
                )
                return default_cmd.replace(cmd_name, cand)
        cls._warn(
            f"swift 子命令 '{cmd_name}' 在当前版本未检测到"
            f"（可用: {sorted(available) or '探测失败'}）。"
            f"将按默认命令执行；若报 no such command，请核对 ms-swift 版本"
            f"（swift --version: {cls.swift_version() or '?'}）并在 SUBCOMMAND_ALIASES 中配置替代子命令"
        )
        return default_cmd

    @classmethod
    def _swift_help_opts(cls, subcommand: str = "pt") -> Set[str]:
        """探测指定子命令（pt/sft/rlhf/export/deploy）的 CLI 选项，结果按子命令缓存。

        背景：ms-swift 不同子命令/版本的模型参数名可能不同
        （`swift pt` 用 `--model_id_or_path`，`swift sft` 可能仍要求 `--model`），
        平台命令需按实际执行的子命令适配，否则 argparse 报 ambiguous
        或 post_init 报 "Please set --model ... model: None"。
        探测失败（swift 未装 / 超时）时返回空集，调用方按默认参数名处理。
        """
        if subcommand in cls._swift_opts_cache:
            return cls._swift_opts_cache[subcommand]
        opts: Set[str] = set()
        try:
            import subprocess
            proc = subprocess.run(
                ["swift", subcommand, "--help"],
                capture_output=True, text=True, timeout=60,
            )
            text = (proc.stdout or "") + (proc.stderr or "")
            opts = set(re.findall(r"(?<!\w)--[a-z][a-z0-9_-]*", text))
        except Exception:
            pass
        cls._swift_opts_cache[subcommand] = opts
        return opts

    @classmethod
    def _resolve_flag(cls, flag: str, subcommand: str = "pt") -> str:
        """把平台默认 CLI flag 适配到指定 swift 子命令（版本改名 / 连字符形式）。

        优先级：
        1. 原始 flag 在探测到的选项集里 → 原样返回；
        2. 下划线→连字符形式命中 → 返回连字符形式；
        3. 跨版本改名映射（renamed）命中探测到的选项集 → 返回改名后的 flag；
        4. 探测失败或未命中任何已知选项 → 返回 renamed 映射中的首个候选（现代标准名），
           而不是盲目透传原始 flag。因为 help 探测可能因版本输出格式差异而漏掉某些参数，
           盲目透传一个已废弃的旧参数名（如 --lora_target_modules → --target_modules）
           会让 swift argparse 报 remaining_argv 错误，导致训练无法启动。
        """
        # 稳定标准参数：这些名字在 MS-Swift 各版本（2.x/3.x/4.x）中长期一致，直接使用，
        # 不参与 help 探测改名。help 探测可能因输出格式/文档文字误扫而返回不准确结果
        # （例如把 --model_id_or_path 当选项列出，但 swift 实际只认 --model），
        # 若据此改名会生成 swift 不接受的参数（报 Please set --model 或 remaining_argv）。
        STABLE_FLAGS = frozenset({
            "--model", "--dataset", "--tuner_type",
            "--learning_rate", "--max_length", "--num_train_epochs",
            "--per_device_train_batch_size",
        })
        if flag in STABLE_FLAGS:
            return flag

        opts = cls._swift_help_opts(subcommand)
        if opts and flag in opts:
            return flag
        # 下划线 → 连字符（如 --learning_rate → --learning-rate）
        hyphen = flag.replace("_", "-")
        if opts and hyphen in opts:
            return hyphen
        # 基础参数跨版本改名映射（2.x/3.x/4.x 参数名差异，按探测到的选项集适配）
        renamed = {
            "--model": ("--model", "--model_id_or_path", "--model-id-or-path", "--model_path"),
            "--dataset": ("--dataset", "--dataset_id_or_path", "--dataset-id-or-path", "--train_dataset", "--train-dataset"),
            "--output_dir": ("--output-dir", "--output_dir"),
            "--tuner_type": ("--train_type", "--train-type", "--tuner-type"),
            "--train_type": ("--tuner_type", "--tuner-type", "--train-type"),
            # 新版（4.x）已把 --lora_target_modules 改名为 --target_modules；首个候选即当前标准名
            "--lora_target_modules": ("--target_modules", "--lora-target-modules", "--target-modules"),
            "--target_modules": ("--lora_target_modules", "--lora-target-modules", "--target-modules"),
            "--rlhf_type": ("--rlhf-type",),
            "--quant_method": ("--quant-method",),
            "--quant_bits": ("--quant-bits",),
            "--calib_dataset": ("--calib-dataset", "--calib_dataset"),
            "--calib_samples": ("--calib-samples",),
        }
        candidates = renamed.get(flag, ())
        if opts:
            for cand in candidates:
                if cand in opts:
                    return cand
        # 探测失败（opts 为空）或未命中任何已知选项：
        # 对已知改名参数，回退到首个候选（现代标准名），避免透传已废弃的旧参数名。
        if flag in renamed:
            return renamed[flag][0]
        return flag

    @staticmethod
    def _value_in_choices(value: Any, choices: List[Any]) -> bool:
        """类型宽容的成员判断：前端表单以字符串提交数值（如 '0.0001'、'5e-5'），
        与契约中的浮点 choices（0.0001、5e-05）需按数值比较而非字符串严格比较。"""
        if value in choices:
            return True
        try:
            fv = float(value)
        except (TypeError, ValueError):
            return False
        for c in choices:
            try:
                if float(c) == fv:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    @classmethod
    def resolve_hyper_params(
        cls,
        hyper: Dict[str, Any],
        start_params: Optional[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """算子参数契约：回填默认值 + 必填/取值校验

        start_params 支持两种格式：
        1. 平面契约（推荐，与前端新默认一致）：
           {"param": 默认值}                     # 标量即默认值，任务未填时回填
           {"param": {"default": .., "required": bool, "choices": [...]}}
        2. 旧版分组结构（兼容历史数据）：
           {"分组名": [{"attr1"/"name": 参数名, "default": .., "required": .., "choices": [...]}, ...]}

        返回 (合并后的超参, 错误信息)；错误信息非空表示校验失败。
        """
        if not start_params:
            return dict(hyper), None

        # 兼容旧版分组结构：值中存在 list 即视为分组定义表，拍平为平面契约
        if any(isinstance(v, list) for v in start_params.values()):
            contract: Dict[str, Any] = {}
            for _group, items in start_params.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("attr1") or item.get("name") or item.get("attr")
                    if not isinstance(name, str) or not name:
                        continue
                    contract[name] = {
                        "default": item.get("default"),
                        "required": bool(item.get("required", False)),
                        "choices": item.get("choices"),
                    }
            start_params = contract

        merged = dict(hyper)
        for key, spec in start_params.items():
            if isinstance(spec, dict):
                default = spec.get("default")
                required = bool(spec.get("required", False))
                choices = spec.get("choices")
            else:
                default = spec
                required = False
                choices = None

            value = merged.get(key)
            if value is None or value == "":
                if default is not None:
                    merged[key] = default
                elif required:
                    return hyper, f"缺少算子必填超参「{key}」"
            else:
                if choices and not cls._value_in_choices(value, choices):
                    return hyper, f"超参「{key}」取值 {value} 不在允许范围 {choices} 内"
        return merged, None

    @classmethod
    def build_train_command(
        cls,
        task_type: str,
        sub_type: Optional[str],
        base_model: str,
        dataset: str,
        output_dir: str,
        hyper_params: Dict[str, Any],
        env_vars: Dict[str, str],
        command_template: Optional[str] = None,
    ) -> List[str]:
        """生成训练 CLI 命令

        两种模式：
        - command_template 为空：平台默认拼接（任务类型 → swift 子命令 + 基础参数 + 超参映射）
        - command_template 非空：算子版本 start_cmd 命令模板，渲染占位符
          {subcommand} {task_type} {sub_type} {model} {dataset} {output_dir}
          渲染后仍追加任务超参（模板中已出现的参数自动跳过，避免重复传参）。
        环境变量由 executor 通过子进程环境变量注入，不追加到命令行。
        """
        subcommand = cls._resolve_subcommand(cls.TASK_CMD_MAP.get(task_type, "swift sft"))
        # 实际执行的子命令名（pt / sft / rlhf / export / train / infer），参数探测按它进行
        cmd_name = subcommand.split()[-1]

        if command_template:
            rendered = (
                command_template
                .replace("{subcommand}", subcommand)
                .replace("{task_type}", task_type or "")
                .replace("{sub_type}", sub_type or "")
                .replace("{model}", base_model or "")
                .replace("{dataset}", dataset or "")
                .replace("{output_dir}", output_dir)
            )
            parts = shlex.split(rendered)
            rendered_text = " ".join(parts)
        else:
            parts = subcommand.split()
            if base_model:
                parts.extend([cls._resolve_flag("--model", cmd_name), base_model])
            if dataset:
                parts.extend([cls._resolve_flag("--dataset", cmd_name), dataset])
            parts.extend([cls._resolve_flag("--output_dir", cmd_name), output_dir])
            # 偏好对齐类型（DPO/KTO/ORPO/SimPO 等离线方法；--rlhf_type 参数名按版本探测适配）
            if task_type == "alignment" and sub_type:
                swift_type = cls.RLHF_TYPE_MAP.get(sub_type)
                if swift_type:
                    parts.extend([cls._resolve_flag("--rlhf_type", cmd_name), swift_type])
            rendered_text = " ".join(parts)

        # 超参数映射（平台内部字段跳过，仅入库回显；模板中已出现的参数跳过，避免重复传参）
        for key, value in hyper_params.items():
            # 平台内部字段：仅用于页面选择/入库回显或控制逻辑，不出现在 swift 命令中
            if key in cls.PLATFORM_INTERNAL_KEYS:
                continue
            swift_param = cls.PARAM_MAP.get(key)
            flag = cls._resolve_flag(swift_param or f"--{key}", cmd_name)
            if flag in rendered_text:
                continue
            parts.extend([flag, str(value)])

        # 环境变量不再以 --env 追加到命令行（ms-swift 各版本对该参数支持不一致，且
        # 4.x 可能直接报 unrecognized arguments）；由 executor 通过 build_process_env()
        # 写入子进程环境变量，效果等价且无参数风险。
        # 关闭 swift 3.x 默认的 v{N}-{时间戳} 版本子目录，保证产物直接落 output_dir
        cls._append_no_version_flag(parts, cmd_name)
        return parts

    @classmethod
    def build_inference_command(
        cls,
        model_path: str,
        framework: str = "vLLM",
        port: int = 8000,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """生成推理 CLI 命令"""
        if framework == "vLLM":
            # vLLM >=0.6 官方推荐 `vllm serve`；旧入口 python -m vllm.entrypoints.openai.api_server
            # 已弃用（未来版本可能移除），作为回退保留。
            if "serve" in cls._vllm_subcommands():
                cmd = [
                    "vllm", "serve",
                    model_path,
                    "--port", str(port),
                ]
            else:
                cmd = [
                    "python", "-m", "vllm.entrypoints.openai.api_server",
                    "--model", model_path,
                    "--port", str(port),
                ]
            if params:
                for key, value in params.items():
                    cmd.extend([f"--{key.replace('_', '-')}", str(value)])
            return cmd

        elif framework == "MindIE":
            cmd = cls._resolve_subcommand("swift deploy").split()
            cmd.extend([
                cls._resolve_flag("--model", cmd[-1]), model_path,
                "--port", str(port),
                "--infer_backend", "mindie",
            ])
            return cmd

        # 默认 Swift deploy
        cmd = cls._resolve_subcommand("swift deploy").split()
        cmd.extend([
            cls._resolve_flag("--model", cmd[-1]), model_path,
            "--port", str(port),
        ])
        if params:
            for key, value in params.items():
                cmd.extend([f"--{key}", str(value)])
        return cmd

    @classmethod
    def is_lora_checkpoint_dir(cls, path: str) -> bool:
        """判断目录是否为 LoRA adapter checkpoint 目录（而非完整模型目录）。

        LoRA 训练产物目录特征：含 adapter_config.json / adapter_model.safetensors，
        且不含完整模型的 model-*.safetensors / pytorch_model*.bin。这样的目录无法被
        vLLM / swift deploy 直接加载，必须先合并回基座模型。
        """
        p = Path(path)
        if not p.is_dir():
            return False
        has_adapter = (p / "adapter_config.json").exists() or (p / "adapter_model.safetensors").exists()
        # 若子目录含 checkpoint-N/adapter_config.json，同样视为 LoRA 产物（根目录可能是
        # 训练输出根目录，checkpoint 在子目录中）
        if not has_adapter:
            try:
                for child in p.iterdir():
                    if child.is_dir() and (
                        (child / "adapter_config.json").exists()
                        or (child / "adapter_model.safetensors").exists()
                    ):
                        has_adapter = True
                        break
            except OSError:
                pass
        if not has_adapter:
            return False
        # 完整模型权重文件：model-*.safetensors 或 pytorch_model*.bin 出现即视为完整模型
        has_full_weight = any(
            p.glob("model-*.safetensors")
        ) or any(p.glob("pytorch_model*.bin"))
        return not has_full_weight

    @classmethod
    def _append_no_version_flag(cls, cmd: List[str], cmd_name: str) -> None:
        """追加 `--add_version false`（若当前 swift 支持）。

        ms-swift 3.x+ 默认会在 --output_dir 下再创建 v{N}-{时间戳} 版本子目录，
        导致 checkpoint 产物比平台预期深一层、顶层目录无 config.json，
        LoRA 检测与产物校验/入库路径全部失效。关闭该行为可让产物直接落
        output_dir。旧版本 swift 无此参数（本就不建版本目录），不追加。
        """
        opts = cls._swift_help_opts(cmd_name)
        if not opts or "--add_version" not in opts:
            return
        if "--add_version" in " ".join(cmd):
            return
        cmd.extend(["--add_version", "false"])

    @classmethod
    def find_lora_adapter_dir(cls, path: str) -> Optional[str]:
        """在训练输出目录中定位 LoRA adapter checkpoint 目录。

        优先使用目录自身（若它直接就是 adapter 目录）；否则递归扫描其下的
        checkpoint-N 子目录（ms-swift 3.x 可能隔着一层 v{N}-{时间戳} 版本
        目录，故不限定深度），返回 step 最大的一个。
        """
        p = Path(path)
        if not p.is_dir():
            return None
        if (p / "adapter_config.json").exists() and (p / "adapter_model.safetensors").exists():
            return str(p)
        candidates = []
        try:
            for child in p.rglob("checkpoint-*"):
                if not child.is_dir():
                    continue
                if not (child / "adapter_config.json").exists():
                    continue
                try:
                    step = int(child.name.split("-")[-1])
                except ValueError:
                    step = -1
                candidates.append((step, str(child)))
        except OSError:
            return None
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[-1][1]

    @classmethod
    def build_merge_command(
        cls,
        base_model: str,
        adapter_dir: str,
        output_dir: str,
    ) -> List[str]:
        """生成 LoRA 权重合并命令（swift export --merge_lora）。

        将训练产出的 LoRA adapter 增量权重合并回基座模型，生成一个可直接被
        vLLM / swift deploy 加载的完整模型目录。这是 LoRA 微调产物「可部署化」
        的关键一步。
        """
        cmd = cls._resolve_subcommand("swift export").split()
        cmd_name = cmd[-1]
        cmd.extend([cls._resolve_flag("--model", cmd_name), base_model])
        # ms-swift 新旧版本参数差异：--adapters（推荐）或 --ckpt_dir（旧版）
        adapter_opt = "--adapters"
        opts = cls._swift_help_opts(cmd_name)
        if opts and "--adapters" not in opts and "--ckpt_dir" in opts:
            adapter_opt = "--ckpt_dir"
        cmd.extend([adapter_opt, adapter_dir])
        cmd.extend([cls._resolve_flag("--merge_lora", cmd_name), "true"])
        cmd.extend([cls._resolve_flag("--output_dir", cmd_name), output_dir])
        # 若输出目录已存在，允许覆盖（幂等重试）
        cmd.append("--exist_ok")
        cmd.append("true")
        # 关闭 swift 3.x 默认的版本子目录，保证合并产物直接落 output_dir
        cls._append_no_version_flag(cmd, cmd_name)
        return cmd

    @classmethod
    def build_export_command(
        cls,
        model_path: str,
        quant_method: str = "bnb",
        output_dir: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """生成模型量化/导出命令（演示版仅支持量化：awq/gptq/bnb/gguf）

        params 中可含 quant_bits / group_size / calib_dataset / calib_samples
        等 swift export 合法参数（flag 名按版本探测适配）；剪枝/蒸馏等展示字段
        在 EXPORT_INTERNAL_KEYS 中被过滤，不会透传给 swift。
        """
        cmd = cls._resolve_subcommand("swift export").split()
        cmd_name = cmd[-1]
        cmd.extend([cls._resolve_flag("--model", cmd_name), model_path])
        if quant_method:
            cmd.extend([cls._resolve_flag("--quant_method", cmd_name), quant_method])
        if output_dir:
            cmd.extend([cls._resolve_flag("--output_dir", cmd_name), output_dir])
        if params:
            for key, value in params.items():
                # 页面展示字段（剪枝/蒸馏/教师模型等）仅入库回显，swift export 不识别，透传会报错
                if key in cls.EXPORT_INTERNAL_KEYS:
                    continue
                flag = cls._resolve_flag(f"--{key}", cmd_name)
                if flag in cmd:
                    continue  # 已出现（显式参数）则跳过，避免重复传参
                cmd.extend([flag, str(value)])
        # 关闭 swift 3.x 默认的版本子目录，保证量化产物直接落 output_dir
        cls._append_no_version_flag(cmd, cmd_name)
        return cmd

    @classmethod
    def parse_loss_from_log(cls, line: str) -> Optional[float]:
        """从日志行解析 Loss 值"""
        if "loss" in line.lower():
            try:
                # 匹配常见的 loss=xxx 格式
                import re
                match = re.search(r'loss[=\s]+([\d.]+)', line)
                if match:
                    return float(match.group(1))
            except (ValueError, IndexError):
                pass
        return None

    @classmethod
    def parse_lr_from_log(cls, line: str) -> Optional[float]:
        """从日志行解析 Learning Rate"""
        import re
        match = re.search(r'(?:lr|learning_rate)[=\s]+([\deE.\-+]+)', line, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None
