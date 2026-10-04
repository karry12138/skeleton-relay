"""TASKS.md 的解析、校验、排序与回写。

TASKS.md 是普通 Markdown，每个任务对应一个信息串为 ``yaml task`` 的代码块；
块外的文字只给人看，解析时忽略，回写时原样保留。
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

STATUSES = ("todo", "done", "blocked")
FIELDS = (
    "id",
    "title",
    "depends_on",
    "files",
    "read_only",
    "instructions",
    "acceptance",
    "status",
    "attempts",
    "last_error",
)
REQUIRED = ("id", "title", "files", "instructions", "acceptance")

_OPEN_RE = re.compile(r"^```yaml[ \t]+task[ \t]*$", re.M)
_BLOCK_RE = re.compile(r"^```yaml[ \t]+task[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class TaskFormatError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass
class Task:
    id: str
    title: str
    files: list[str]
    instructions: str
    acceptance: list[str]
    depends_on: list[str] = field(default_factory=list)
    read_only: list[str] = field(default_factory=list)
    status: str = "todo"
    attempts: int = 0
    last_error: str | None = None
    line: int = field(default=0, compare=False, repr=False)

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in FIELDS}


@dataclass
class TaskFile:
    path: Path
    text: str
    tasks: list[Task]

    def get(self, task_id: str) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(task_id)


def _is_str_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _parse_block(body: str, line: int) -> tuple[Task | None, list[str]]:
    where = f"第 {line} 行的任务块"
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        return None, [f"{where}：YAML 解析失败：{exc}"]
    if not isinstance(data, dict):
        return None, [f"{where}：内容必须是映射（key: value）"]

    errors = []
    unknown = sorted(set(data) - set(FIELDS))
    if unknown:
        errors.append(f"{where}：未知字段 {unknown}，允许的字段为 {list(FIELDS)}")
    missing = [name for name in REQUIRED if name not in data]
    if missing:
        errors.append(f"{where}：缺少必填字段 {missing}")
    if errors:
        return None, errors

    data.setdefault("depends_on", [])
    data.setdefault("read_only", [])
    data.setdefault("status", "todo")
    data.setdefault("attempts", 0)
    data.setdefault("last_error", None)

    if not isinstance(data["id"], str) or not _ID_RE.match(data["id"]):
        errors.append(f"{where}：id 必须是字母数字/._- 组成的字符串（纯数字请加引号）：{data['id']!r}")
    where = f"任务 {data['id']}（第 {line} 行）"
    if not isinstance(data["title"], str) or not data["title"].strip():
        errors.append(f"{where}：title 必须是非空字符串")
    if not isinstance(data["instructions"], str) or not data["instructions"].strip():
        errors.append(f"{where}：instructions 必须是非空字符串")
    for name in ("depends_on", "files", "read_only", "acceptance"):
        if not _is_str_list(data[name]):
            errors.append(f"{where}：{name} 必须是字符串列表")
    for name in ("files", "acceptance"):
        if _is_str_list(data[name]) and not data[name]:
            errors.append(f"{where}：{name} 不能为空")
    if data["status"] not in STATUSES:
        errors.append(f"{where}：status 必须是 {STATUSES} 之一：{data['status']!r}")
    if not isinstance(data["attempts"], int) or isinstance(data["attempts"], bool) or data["attempts"] < 0:
        errors.append(f"{where}：attempts 必须是非负整数")
    if data["last_error"] is not None and not isinstance(data["last_error"], str):
        errors.append(f"{where}：last_error 必须是字符串或 null")
    if errors:
        return None, errors

    return Task(line=line, **data), []


def parse_tasks(text: str) -> list[Task]:
    tasks, errors = [], []
    matches = list(_BLOCK_RE.finditer(text))
    if len(matches) != len(_OPEN_RE.findall(text)):
        errors.append("存在未闭合的 ```yaml task 代码块")
    for m in matches:
        line = text.count("\n", 0, m.start()) + 1
        task, block_errors = _parse_block(m.group(1), line)
        errors.extend(block_errors)
        if task:
            tasks.append(task)
    if not matches and not errors:
        errors.append("没有找到任何 ```yaml task 代码块")
    if errors:
        raise TaskFormatError(errors)
    return tasks


def load_tasks(path: str | Path) -> TaskFile:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return TaskFile(path=path, text=text, tasks=parse_tasks(text))


class _Dumper(yaml.SafeDumper):
    pass


def _represent_str(dumper: yaml.SafeDumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def dump_task(task: Task) -> str:
    return yaml.dump(
        task.to_dict(),
        Dumper=_Dumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )


def render_tasks(tf: TaskFile) -> str:
    by_id = {task.id: task for task in tf.tasks}

    def replace(m: re.Match) -> str:
        task_id = yaml.safe_load(m.group(1))["id"]
        return f"```yaml task\n{dump_task(by_id[task_id])}```"

    return _BLOCK_RE.sub(replace, tf.text)


def save_tasks(tf: TaskFile) -> None:
    tf.text = render_tasks(tf)
    with open(tf.path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(tf.text)


def _norm(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def validate(tasks: list[Task], protected: list[str] = ()) -> list[str]:
    """语义校验：id 唯一、依赖存在且无环、可写文件不与只读/受保护文件重叠。"""
    errors = []
    ids = [task.id for task in tasks]
    seen = set()
    for task_id in ids:
        if task_id in seen:
            errors.append(f"任务 id 重复：{task_id}")
        seen.add(task_id)

    for task in tasks:
        where = f"任务 {task.id}（第 {task.line} 行）"
        for dep in task.depends_on:
            if dep == task.id:
                errors.append(f"{where}：不能依赖自身")
            elif dep not in seen:
                errors.append(f"{where}：depends_on 引用了不存在的任务 {dep}")
        files = {_norm(p) for p in task.files}
        overlap = sorted(files & {_norm(p) for p in task.read_only})
        if overlap:
            errors.append(f"{where}：文件同时出现在 files 和 read_only 中：{overlap}")
        for path in sorted(files):
            hits = [pat for pat in protected if fnmatch.fnmatchcase(path, _norm(pat))]
            if hits:
                errors.append(f"{where}：files 中的 {path} 命中受保护规则 {hits}")

    if not errors:
        try:
            topo_sort(tasks)
        except TaskFormatError as exc:
            errors.extend(exc.errors)
    return errors


def topo_sort(tasks: list[Task]) -> list[Task]:
    """按依赖排序；无依赖关系的任务保持在文件中的先后顺序。"""
    order = {task.id: i for i, task in enumerate(tasks)}
    pending = {task.id: set(task.depends_on) for task in tasks}
    by_id = {task.id: task for task in tasks}
    result = []
    while pending:
        ready = sorted((tid for tid, deps in pending.items() if not deps), key=order.get)
        if not ready:
            raise TaskFormatError([f"依赖存在环：{sorted(pending)}"])
        tid = ready[0]
        result.append(by_id[tid])
        del pending[tid]
        for deps in pending.values():
            deps.discard(tid)
    return result


def runnable(tasks: list[Task]) -> list[Task]:
    """按依赖顺序返回状态为 todo、且所有依赖均已 done 的任务。"""
    status = {task.id: task.status for task in tasks}
    return [
        task
        for task in topo_sort(tasks)
        if task.status == "todo" and all(status[dep] == "done" for dep in task.depends_on)
    ]
