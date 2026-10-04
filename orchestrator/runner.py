"""脚本版编排循环：按依赖逐任务执行 → 接口保护 → 验收测试 → 回写状态。"""

from __future__ import annotations

import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import RelayConfig, load_config
from .executors import ExecResult, run_aider
from .guard import check_task, run_git
from .prompt import build_prompt
from .tasks import Task, TaskFile, TaskFormatError, load_tasks, runnable, save_tasks, validate

_ERROR_LIMIT = 3000


@dataclass
class AttemptRecord:
    attempt: int
    exec_returncode: int
    timed_out: bool
    duration: float
    tokens_sent: int
    tokens_received: int
    format_errors: int
    commits: int
    guard_errors: list[str]
    tests_passed: bool
    test_tail: str


@dataclass
class TaskRecord:
    id: str
    status: str
    attempts: list[AttemptRecord] = field(default_factory=list)


def acceptance_cmd(config: RelayConfig, task: Task) -> str:
    return config.test_cmd.format(acceptance=" ".join(task.acceptance))


def run_tests(root: Path, cmd: str) -> tuple[bool, str]:
    proc = subprocess.run(
        cmd, cwd=root, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-40:])
    return proc.returncode == 0, tail


def _head(root: Path) -> str:
    return run_git(root, "rev-parse", "HEAD").strip()


def _rollback(root: Path, base: str) -> None:
    run_git(root, "reset", "--hard", base)
    run_git(root, "clean", "-fd")


def _commit_tasks(root: Path, tf: TaskFile, message: str) -> None:
    save_tasks(tf)
    run_git(root, "add", "--", str(tf.path.relative_to(root)))
    run_git(root, "-c", "user.name=skeleton-relay", "-c", "user.email=relay@localhost",
            "commit", "-q", "--allow-empty", "-m", message)


def _failure_text(guard_errors: list[str], tests_passed: bool, test_tail: str, result: ExecResult) -> str:
    parts = []
    if result.timed_out:
        parts.append(f"执行超时（{result.duration:.0f} 秒）")
    if guard_errors:
        parts.append("接口保护检查失败：\n" + "\n".join(guard_errors))
    if not tests_passed:
        parts.append("验收测试失败：\n" + test_tail)
    return "\n\n".join(parts)[-_ERROR_LIMIT:]


def run_task(root: Path, tf: TaskFile, task: Task, config: RelayConfig, log_dir: Path) -> TaskRecord:
    record = TaskRecord(id=task.id, status=task.status)
    test_cmd = acceptance_cmd(config, task)
    while task.attempts < config.executor.max_attempts:
        base = _head(root)
        task.attempts += 1
        result = run_aider(root, task, config.executor, build_prompt(task), test_cmd, log_dir, task.attempts)
        commits = int(run_git(root, "rev-list", "--count", f"{base}..HEAD").strip())
        guard_errors = check_task(root, task, config, base)
        tests_passed, test_tail = run_tests(root, test_cmd)
        record.attempts.append(AttemptRecord(
            attempt=task.attempts,
            exec_returncode=result.returncode,
            timed_out=result.timed_out,
            duration=round(result.duration, 1),
            tokens_sent=result.tokens_sent,
            tokens_received=result.tokens_received,
            format_errors=result.format_errors,
            commits=commits,
            guard_errors=guard_errors,
            tests_passed=tests_passed,
            test_tail=test_tail,
        ))
        if tests_passed and not guard_errors and not result.timed_out:
            task.status, task.last_error = "done", None
            _commit_tasks(root, tf, f"relay: {task.id} done")
            break
        task.last_error = _failure_text(guard_errors, tests_passed, test_tail, result)
        _rollback(root, base)
    else:
        task.status = "blocked"
    if task.status != "done":
        _commit_tasks(root, tf, f"relay: {task.id} {task.status}")
    record.status = task.status
    return record


def run(root: str | Path, log_dir: str | Path, config: RelayConfig | None = None) -> list[TaskRecord]:
    root, log_dir = Path(root), Path(log_dir)
    config = config or load_config(root / "relay.yaml")
    tf = load_tasks(root / config.tasks_file)
    errors = validate(tf.tasks, config.protected)
    if errors:
        raise TaskFormatError(errors)
    records = []
    while ready := runnable(tf.tasks):
        task = ready[0]
        print(f"[{time.strftime('%H:%M:%S')}] {task.id} {task.title} 开始", flush=True)
        record = run_task(root, tf, task, config, log_dir)
        took = sum(a.duration for a in record.attempts)
        print(f"[{time.strftime('%H:%M:%S')}] {task.id} -> {record.status}"
              f"（尝试 {len(record.attempts)} 次，共 {took:.0f}s）", flush=True)
        records.append(record)
    return records


def records_to_json(records: list[TaskRecord]) -> list[dict]:
    return [asdict(r) for r in records]
