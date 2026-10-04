"""目标项目根目录下 relay.yaml 的加载。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

THINKING_LEVELS = ("off", "low", "high", "max")

@dataclass
class ExecutorConfig:
    kind: str = "aider"
    base_url: str = ""
    model: str = ""
    api_key: str = "sk-local"
    max_attempts: int = 3
    edit_format: str = "diff"
    thinking: str = "off"              # off | low | high | max；服务端补丁把其余取值都映射为 low
    temperature: float | None = 0.0    # None 表示不发送，由 vLLM 服务端默认采样决定
    max_tokens: int = 32768
    context_window: int = 1048576
    timeout: int = 900

    def __post_init__(self) -> None:
        if isinstance(self.thinking, bool):
            self.thinking = "high" if self.thinking else "off"
        if self.thinking not in THINKING_LEVELS:
            raise ValueError(f"thinking 必须是 {THINKING_LEVELS} 之一：{self.thinking!r}")


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
