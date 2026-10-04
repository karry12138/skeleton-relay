from pathlib import Path

import pytest

from orchestrator.__main__ import main
from orchestrator.tasks import (
    TaskFormatError,
    load_tasks,
    parse_tasks,
    render_tasks,
    runnable,
    save_tasks,
    topo_sort,
    validate,
)

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def block(body: str) -> str:
    return f"## 任务\n\n```yaml task\n{body}```\n"


MINIMAL = """\
id: A
title: a
files: [src/a.py]
instructions: do a
acceptance: [tests/test_a.py]
"""


def test_template_is_valid():
    tf = load_tasks(TEMPLATES / "TASKS.md")
    assert [t.id for t in tf.tasks] == ["T001", "T002", "T003"]
    assert validate(tf.tasks, ["SPEC.md", "relay.yaml", "tests/*"]) == []


def test_template_round_trip_is_byte_identical():
    tf = load_tasks(TEMPLATES / "TASKS.md")
    assert render_tasks(tf) == tf.text


def test_defaults_applied():
    (task,) = parse_tasks(block(MINIMAL))
    assert task.depends_on == [] and task.read_only == []
    assert (task.status, task.attempts, task.last_error) == ("todo", 0, None)


def test_save_updates_only_task_blocks(tmp_path):
    path = tmp_path / "TASKS.md"
    path.write_text("# 标题\n\n说明文字\n\n" + block(MINIMAL) + "\n结尾\n", encoding="utf-8")
    tf = load_tasks(path)
    task = tf.get("A")
    task.status, task.attempts, task.last_error = "blocked", 3, "AssertionError: 1 != 2\n  at line 3"
    save_tasks(tf)

    text = path.read_text(encoding="utf-8")
    assert text.startswith("# 标题\n\n说明文字\n\n") and text.endswith("\n结尾\n")
    (reloaded,) = load_tasks(path).tasks
    assert reloaded.status == "blocked"
    assert reloaded.last_error == "AssertionError: 1 != 2\n  at line 3"


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_save_preserves_newline_style(tmp_path, newline):
    path = tmp_path / "TASKS.md"
    path.write_bytes(("# T\n\n" + block(MINIMAL)).replace("\n", newline).encode("utf-8"))
    save_tasks(load_tasks(path))
    original = path.read_bytes()
    assert original.count(newline.encode()) == original.count(b"\n")

    tf = load_tasks(path)
    tf.get("A").status = "done"
    save_tasks(tf)
    before, after = original.split(b"\n"), path.read_bytes().split(b"\n")
    assert len(before) == len(after)
    assert [a for a, b in zip(after, before) if a != b] == [("status: done" + newline).rstrip("\n").encode()]


@pytest.mark.parametrize(
    "body, message",
    [
        (MINIMAL.replace("id: A", "id: 001"), "id 必须"),
        (MINIMAL + "statuz: done\n", "未知字段"),
        (MINIMAL.replace("acceptance: [tests/test_a.py]\n", ""), "缺少必填字段"),
        (MINIMAL.replace("[tests/test_a.py]", "[]"), "acceptance 不能为空"),
        (MINIMAL.replace("files: [src/a.py]", "files: src/a.py"), "files 必须是字符串列表"),
        (MINIMAL + "status: doing\n", "status 必须"),
        ("- not a mapping\n", "必须是映射"),
    ],
)
def test_block_errors(body, message):
    with pytest.raises(TaskFormatError) as exc:
        parse_tasks(block(body))
    assert any(message in e for e in exc.value.errors), exc.value.errors


def test_unclosed_block():
    with pytest.raises(TaskFormatError, match="未闭合"):
        parse_tasks(block(MINIMAL) + "```yaml task\nid: B\n")


def make(id, deps=(), files=("src/x.py",), read_only=(), status="todo"):
    body = MINIMAL.replace("id: A", f"id: {id}").replace("[src/a.py]", f"[{', '.join(files)}]")
    body += f"depends_on: [{', '.join(deps)}]\nread_only: [{', '.join(read_only)}]\nstatus: {status}\n"
    return parse_tasks(block(body))[0]


def test_validate_semantic_errors():
    tasks = [
        make("A", deps=["Z"]),
        make("A"),
        make("B", files=["src/b.py"], read_only=["./src/b.py"]),
        make("C", files=["tests/test_c.py"]),
    ]
    errors = "\n".join(validate(tasks, ["tests/*"]))
    assert "id 重复" in errors
    assert "不存在的任务 Z" in errors
    assert "同时出现在 files 和 read_only" in errors
    assert "命中受保护规则" in errors


def test_cycle_detected():
    errors = validate([make("A", deps=["B"]), make("B", deps=["A"])])
    assert any("环" in e for e in errors)


def test_topo_sort_is_stable():
    tasks = [make("C", deps=["A"]), make("B"), make("A")]
    assert [t.id for t in topo_sort(tasks)] == ["B", "A", "C"]


def test_runnable_requires_done_dependencies():
    tasks = [make("A", status="done"), make("B", deps=["A"]), make("C", deps=["B"]), make("D", status="blocked")]
    assert [t.id for t in runnable(tasks)] == ["B"]


def test_cli_validate(tmp_path, capsys):
    (tmp_path / "TASKS.md").write_text((TEMPLATES / "TASKS.md").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "relay.yaml").write_text((TEMPLATES / "relay.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["validate", str(tmp_path)]) == 0
    assert main(["list", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "* T001" in out and "  T002" in out
