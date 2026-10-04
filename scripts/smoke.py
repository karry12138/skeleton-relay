"""冒烟测试：把示例骨架拷进沙箱，定稿打 tag，再用执行模型逐任务实现。

用法：
    python scripts/smoke.py --example examples/calc --thinking off
    python scripts/smoke.py --example examples/calc --thinking on --max-attempts 2
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator.config import load_config  # noqa: E402
from orchestrator.guard import run_git  # noqa: E402
from orchestrator.runner import records_to_json, run  # noqa: E402


def setup_sandbox(example: Path, project: Path) -> None:
    shutil.copytree(example, project, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    ident = ("-c", "user.name=skeleton-relay", "-c", "user.email=relay@localhost")
    run_git(project, "init", "-q", "-b", "main")
    run_git(project, "config", "core.autocrlf", "false")
    run_git(project, "add", "-A")
    run_git(project, *ident, "commit", "-q", "-m", "skeleton: 定稿")
    run_git(project, "tag", "skeleton-v1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--example", type=Path, default=REPO / "examples" / "calc")
    parser.add_argument("--thinking", choices=["on", "off"], default="off")
    parser.add_argument("--edit-format", default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--name", default=None)
    args = parser.parse_args()

    name = args.name or f"{args.example.name}-{args.thinking}"
    run_dir = REPO / "sandbox" / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
    project, log_dir = run_dir / "project", run_dir / "logs"
    setup_sandbox(args.example.resolve(), project)

    config = load_config(project / "relay.yaml")
    config.executor.thinking = args.thinking == "on"
    if args.edit_format:
        config.executor.edit_format = args.edit_format
    if args.temperature is not None:
        config.executor.temperature = args.temperature
    if args.max_attempts:
        config.executor.max_attempts = args.max_attempts

    print(f"沙箱：{run_dir}")
    print(f"模型：{config.executor.model} @ {config.executor.base_url}  thinking={config.executor.thinking}"
          f"  temperature={config.executor.temperature}  edit_format={config.executor.edit_format}  max_attempts={config.executor.max_attempts}")
    records = run(project, log_dir, config)

    summary = {
        "executor": vars(config.executor),
        "tasks": records_to_json(records),
    }
    (run_dir / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n任务     状态      尝试  耗时(s)  发送/接收 tokens   格式错误  接口违规")
    for r in records:
        dur = sum(a.duration for a in r.attempts)
        sent = sum(a.tokens_sent for a in r.attempts)
        recv = sum(a.tokens_received for a in r.attempts)
        fmt = sum(a.format_errors for a in r.attempts)
        guard = sum(len(a.guard_errors) for a in r.attempts)
        print(f"{r.id:<8} {r.status:<8} {len(r.attempts):>4}  {dur:>7.0f}  {sent:>8}/{recv:<8}  {fmt:>8}  {guard:>8}")
    print(f"\n结果：{run_dir / 'results.json'}")
    return 0 if all(r.status == "done" for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
