"""命令行入口：relay validate / relay list / relay check。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .guard import GitError, check_task
from .tasks import TaskFormatError, load_tasks, runnable, topo_sort, validate


def _load(project: Path):
    config = load_config(project / "relay.yaml")
    return config, load_tasks(project / config.tasks_file)


def _print_errors(errors: list[str]) -> None:
    for err in errors:
        print(f"[错误] {err}")


def cmd_validate(project: Path) -> int:
    try:
        config, tf = _load(project)
    except TaskFormatError as exc:
        _print_errors(exc.errors)
        return 1
    errors = validate(tf.tasks, config.protected)
    if errors:
        _print_errors(errors)
        return 1
    print(f"[通过] {tf.path}：{len(tf.tasks)} 个任务，格式与依赖校验通过")
    return 0


def cmd_list(project: Path) -> int:
    try:
        _, tf = _load(project)
        ordered = topo_sort(tf.tasks)
    except TaskFormatError as exc:
        _print_errors(exc.errors)
        return 1
    ready = {task.id for task in runnable(tf.tasks)}
    for task in ordered:
        mark = "*" if task.id in ready else " "
        deps = ",".join(task.depends_on) or "-"
        print(f"{mark} {task.id:<8} {task.status:<8} deps={deps:<12} {task.title}")
    return 0


def cmd_check(project: Path, task_id: str, base: str) -> int:
    try:
        config, tf = _load(project)
        task = tf.get(task_id)
        errors = check_task(project, task, config, base)
    except TaskFormatError as exc:
        _print_errors(exc.errors)
        return 1
    except KeyError:
        _print_errors([f"任务 {task_id} 不存在"])
        return 1
    except GitError as exc:
        _print_errors([str(exc)])
        return 1
    if errors:
        _print_errors(errors)
        return 1
    print(f"[通过] 任务 {task_id}：接口保护检查通过")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="relay", description="skeleton-relay 编排器")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, help_text in (("validate", "校验 TASKS.md"), ("list", "按依赖顺序列出任务，* 表示当前可执行")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("project", nargs="?", default=".", type=Path, help="目标项目根目录")
    p = sub.add_parser("check", help="检查任务的改动是否违反接口保护")
    p.add_argument("task_id")
    p.add_argument("project", nargs="?", default=".", type=Path, help="目标项目根目录")
    p.add_argument("--base", default="HEAD", help="任务开始前的提交（默认 HEAD，即只看未提交的改动）")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args.project, args.task_id, args.base)
    return {"validate": cmd_validate, "list": cmd_list}[args.cmd](args.project)


if __name__ == "__main__":
    sys.exit(main())
