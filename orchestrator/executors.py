"""执行层：调用 aider + 本地模型实现单个任务。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .config import ExecutorConfig
from .tasks import Task

_FORMAT_ERROR_RE = re.compile(r"SearchReplaceNoExactMatch|did not conform to the edit format|Failed to apply edit")
_TOKENS_RE = re.compile(r"Tokens: ([\d.]+)(k?) sent, ([\d.]+)(k?) received")


@dataclass
class ExecResult:
    returncode: int
    duration: float
    timed_out: bool
    log_path: Path
    tokens_sent: int
    tokens_received: int
    format_errors: int


def _model_name(cfg: ExecutorConfig) -> str:
    return f"openai/{cfg.model}"


def write_model_files(cfg: ExecutorConfig, out_dir: Path) -> tuple[Path, Path]:
    """生成 aider 的模型设置与元数据文件，放在项目目录之外。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    name = _model_name(cfg)
    settings = [
        {
            "name": name,
            "edit_format": cfg.edit_format,
            "use_repo_map": False,
            "use_temperature": cfg.temperature,
            "extra_params": {
                "max_tokens": cfg.max_tokens,
                "extra_body": {"chat_template_kwargs": {"thinking": cfg.thinking}},
            },
        }
    ]
    metadata = {
        name: {
            "max_input_tokens": cfg.context_window,
            "max_output_tokens": cfg.max_tokens,
            "max_tokens": cfg.max_tokens,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
            "litellm_provider": "openai",
            "mode": "chat",
        }
    }
    settings_path = out_dir / "aider.model.settings.yml"
    metadata_path = out_dir / "aider.model.metadata.json"
    settings_path.write_text(yaml.safe_dump(settings, sort_keys=False), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return settings_path, metadata_path


def _env(cfg: ExecutorConfig) -> dict[str, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    host = urlparse(cfg.base_url).hostname or ""
    bypass = ",".join(filter(None, [env.get("NO_PROXY", ""), host, "localhost", "127.0.0.1"]))
    env["NO_PROXY"] = env["no_proxy"] = bypass
    return env


def _count_tokens(text: str) -> tuple[int, int]:
    sent = received = 0
    for s, sk, r, rk in _TOKENS_RE.findall(text):
        sent += int(float(s) * (1000 if sk else 1))
        received += int(float(r) * (1000 if rk else 1))
    return sent, received


def aider_command(
    task: Task, cfg: ExecutorConfig, prompt_path: Path, test_cmd: str,
    settings_path: Path, metadata_path: Path, log_dir: Path,
) -> list[str]:
    cmd = [
        sys.executable, "-m", "aider",
        "--model", _model_name(cfg),
        "--openai-api-base", cfg.base_url,
        "--openai-api-key", cfg.api_key,
        "--model-settings-file", str(settings_path),
        "--model-metadata-file", str(metadata_path),
        "--edit-format", cfg.edit_format,
        "--map-tokens", "0",
        "--message-file", str(prompt_path),
        "--test-cmd", test_cmd,
        "--auto-test",
        "--auto-commits",
        "--no-dirty-commits",
        "--yes-always",
        "--no-pretty",
        "--no-stream",
        "--no-gitignore",
        "--no-check-update",
        "--no-show-release-notes",
        "--no-show-model-warnings",
        "--analytics-disable",
        "--encoding", "utf-8",
        "--chat-history-file", str(log_dir / f"{task.id}.chat.md"),
        "--input-history-file", str(log_dir / f"{task.id}.input.txt"),
        "--llm-history-file", str(log_dir / f"{task.id}.llm.txt"),
    ]
    for path in task.files:
        cmd += ["--file", path]
    for path in task.read_only:
        cmd += ["--read", path]
    return cmd


def run_aider(
    root: Path, task: Task, cfg: ExecutorConfig, prompt: str, test_cmd: str,
    log_dir: Path, attempt: int,
) -> ExecResult:
    log_dir.mkdir(parents=True, exist_ok=True)
    settings_path, metadata_path = write_model_files(cfg, log_dir)
    prompt_path = log_dir / f"{task.id}.attempt{attempt}.prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    log_path = log_dir / f"{task.id}.attempt{attempt}.aider.log"
    cmd = aider_command(task, cfg, prompt_path, test_cmd, settings_path, metadata_path, log_dir)

    start = time.monotonic()
    timed_out = False
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(subprocess.list2cmdline(cmd) + "\n\n")
        log.flush()
        try:
            proc = subprocess.run(
                cmd, cwd=root, env=_env(cfg), stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, timeout=cfg.timeout,
            )
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out, returncode = True, -1
    duration = time.monotonic() - start

    text = log_path.read_text(encoding="utf-8", errors="replace")
    sent, received = _count_tokens(text)
    return ExecResult(
        returncode=returncode,
        duration=duration,
        timed_out=timed_out,
        log_path=log_path,
        tokens_sent=sent,
        tokens_received=received,
        format_errors=len(_FORMAT_ERROR_RE.findall(text)),
    )
