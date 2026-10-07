"""在已定稿的项目里原地执行接力：项目目录必须是独立 git 仓库的根，且已打 skeleton tag。

用法：
    python scripts/run.py D:/path/to/project
    python scripts/run.py D:/path/to/project --thinking off --max-attempts 3

日志与 results.json 写在 sandbox/<时间>-<项目名>-run/ 下，不进项目目录（失败回滚会 clean 项目）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator.config import THINKING_LEVELS, load_config  # noqa: E402
from orchestrator.guard import run_git  # noqa: E402
from orchestrator.runner import records_to_json, run  # noqa: E402


def check_project(project: Path, tag: str) -> None:
    top = Path(run_git(project, "rev-parse", "--show-toplevel").strip()).resolve()
    if top != project:
        raise SystemExit(f"项目目录不是 git 仓库根：{project}（仓库根为 {top}）")
    if run_git(project, "status", "--porcelain").strip():
        raise SystemExit("项目有未提交的改动，先提交或清理再运行")
    run_git(project, "rev-parse", "--verify", f"refs/tags/{tag}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--thinking", choices=THINKING_LEVELS, default=None)
    parser.add_argument("--max-attempts", type=int, default=None)
    args = parser.parse_args()

    project = args.project.resolve()
    config = load_config(project / "relay.yaml")
    check_project(project, config.skeleton_tag)
    if args.thinking:
        config.executor.thinking = args.thinking
    if args.max_attempts:
        config.executor.max_attempts = args.max_attempts

    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    run_dir = REPO / "sandbox" / f"{time.strftime('%Y%m%d-%H%M%S')}-{project.name}-run"
    log_dir = run_dir / "logs"
    print(f"项目：{project}\n日志：{run_dir}")
    print(f"模型：{config.executor.model} @ {config.executor.base_url}  thinking={config.executor.thinking}"
          f"  temperature={config.executor.temperature}  max_attempts={config.executor.max_attempts}", flush=True)
    records = run(project, log_dir, config)

    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {"project": str(project), "executor": vars(config.executor), "tasks": records_to_json(records)}
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
