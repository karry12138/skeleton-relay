"""目标项目根目录下 relay.yaml 的加载。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ExecutorConfig:
    kind: str = "aider"
    base_url: str = ""
    model: str = ""
    max_attempts: int = 3


@dataclass
class RelayConfig:
    skeleton_tag: str = "skeleton-v1"
    tasks_file: str = "TASKS.md"
    test_cmd: str = "python -m pytest -q {acceptance}"
    protected: list[str] = field(default_factory=lambda: ["SPEC.md", "relay.yaml", "tests/*"])
    executor: ExecutorConfig = field(default_factory=ExecutorConfig)


def load_config(path: str | Path) -> RelayConfig:
    path = Path(path)
    if not path.exists():
        return RelayConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    executor = ExecutorConfig(**(data.pop("executor", None) or {}))
    return RelayConfig(executor=executor, **data)
