import subprocess

import pytest

from orchestrator.__main__ import main
from orchestrator.config import RelayConfig
from orchestrator.guard import check_task, compare_signatures, signatures
from orchestrator.tasks import load_tasks

SKELETON = '''\
from dataclasses import dataclass


@dataclass
class Token:
    kind: str
    text: str = ""


class Lexer:
    def __init__(self, source: str) -> None:
        raise NotImplementedError("T001")

    def tokens(self) -> list[Token]:
        """返回全部 token。"""
        raise NotImplementedError("T001")


def tokenize(source: str, *, strict: bool = True) -> list[Token]:
    raise NotImplementedError("T001")
'''

IMPLEMENTED = SKELETON.replace(
    '''    def __init__(self, source: str) -> None:
        raise NotImplementedError("T001")''',
    '''    def __init__(self, source: str) -> None:
        self.source = source

    def _scan(self) -> list[Token]:
        return [Token(kind="NUMBER", text=c) for c in self.source if c.isdigit()]''',
).replace(
    '''        """返回全部 token。"""
        raise NotImplementedError("T001")''',
    '''        """返回全部 token。"""
        def helper(x):
            return x
        return helper(self._scan())''',
).replace(
    'def tokenize(source: str, *, strict: bool = True) -> list[Token]:\n    raise NotImplementedError("T001")',
    'def tokenize(source: str, *, strict: bool = True) -> list[Token]:\n    return _impl(source)\n\n\ndef _impl(s):\n    return Lexer(s).tokens()',
)

TASKS = '''\
```yaml task
id: T001
title: lexer
files:
- src/lexer.py
read_only:
- src/types.py
instructions: do it
acceptance:
- tests/test_lexer.py
```
'''


def test_implementation_keeps_signatures():
    assert compare_signatures("lexer.py", SKELETON, IMPLEMENTED) == []
    assert "Lexer.tokens.helper" not in signatures(IMPLEMENTED)


@pytest.mark.parametrize(
    "old, new, message",
    [
        ("source: str, *, strict", "source: str, *, strict_mode", "修改了 tokenize 的签名"),
        ("-> list[Token]:\n    raise", "-> list:\n    raise", "修改了 tokenize 的签名"),
        ("@dataclass\nclass Token", "class Token", "修改了 Token 的签名"),
        ('text: str = ""', "text: str", "修改了 Token.text 的签名"),
        ("    def tokens(self)", "    def all_tokens(self)", "删除了骨架符号 Lexer.tokens"),
        ("\n\ndef tokenize", "\n\ndef helper():\n    pass\n\n\ndef tokenize", "新增了公开符号 helper"),
        ("class Lexer:", "class Lexer:\n    def peek(self): ...", "新增了公开符号 Lexer.peek"),
        ("class Lexer:", "class Lexer(", "语法错误"),
    ],
)
def test_signature_violations(old, new, message):
    assert old in SKELETON
    errors = compare_signatures("lexer.py", SKELETON, SKELETON.replace(old, new))
    assert any(message in e for e in errors), errors


def git(root, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root, check=True, capture_output=True,
    )


@pytest.fixture
def project(tmp_path):
    files = {
        "src/lexer.py": SKELETON,
        "src/types.py": "KINDS = ('NUMBER',)\n",
        "src/other.py": "X = 1\n",
        "tests/test_lexer.py": "def test_x():\n    pass\n",
        "SPEC.md": "# SPEC\n",
        "TASKS.md": TASKS,
    }
    for path, text in files.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text, encoding="utf-8", newline="\n")
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "skeleton")
    git(tmp_path, "tag", "skeleton-v1")
    return tmp_path


def run_check(root, base="HEAD"):
    task = load_tasks(root / "TASKS.md").get("T001")
    return check_task(root, task, RelayConfig(), base)


def write(root, path, text):
    (root / path).write_text(text, encoding="utf-8", newline="\n")


def test_clean_implementation_passes(project):
    write(project, "src/lexer.py", IMPLEMENTED)
    write(project, "TASKS.md", TASKS.replace("title: lexer", "title: lexer\nstatus: done"))
    assert run_check(project) == []


def test_committed_signature_change_still_caught(project):
    write(project, "src/lexer.py", IMPLEMENTED.replace("strict: bool", "strict: int"))
    git(project, "commit", "-qam", "aider: T001")
    errors = run_check(project, base="HEAD")
    assert any("修改了 tokenize 的签名" in e for e in errors), errors


def test_scope_measured_from_base(project):
    write(project, "src/lexer.py", IMPLEMENTED)
    write(project, "src/other.py", "X = 2\n")
    git(project, "commit", "-qam", "aider: T001")
    assert run_check(project, base="HEAD") == []
    errors = run_check(project, base="skeleton-v1")
    assert any("src/other.py：不在任务 T001 的 files 中" in e for e in errors), errors


def test_frozen_and_out_of_scope(project):
    write(project, "src/lexer.py", IMPLEMENTED)
    write(project, "src/types.py", "KINDS = ('NUMBER', 'PLUS')\n")
    write(project, "tests/test_lexer.py", "def test_x():\n    assert True\n")
    write(project, "src/other.py", "X = 2\n")
    write(project, "src/new_module.py", "Y = 1\n")
    errors = "\n".join(run_check(project))
    assert "src/types.py：冻结文件" in errors
    assert "tests/test_lexer.py：冻结文件" in errors
    assert "src/other.py：不在任务 T001 的 files 中" in errors
    assert "src/new_module.py：不在任务 T001 的 files 中" in errors
    assert "src/types.py：不在任务" not in errors


def test_deleted_skeleton_file(project):
    (project / "src/lexer.py").unlink()
    assert any("骨架文件被删除" in e for e in run_check(project))


def test_earlier_task_changes_do_not_count_as_out_of_scope(project):
    write(project, "src/other.py", "X = 2\n")
    git(project, "commit", "-qam", "T000")
    write(project, "src/lexer.py", IMPLEMENTED)
    assert run_check(project) == []


def test_read_only_implemented_by_earlier_task(project):
    write(project, "src/types.py", "KINDS = ('NUMBER', 'PLUS')\n")
    git(project, "commit", "-qam", "T000")
    write(project, "src/lexer.py", IMPLEMENTED)
    assert run_check(project) == []
    write(project, "src/types.py", "KINDS = ()\n")
    assert any("src/types.py：冻结文件" in e for e in run_check(project))


def test_protected_measured_from_tag(project):
    config = RelayConfig(protected=["SPEC.md"])
    write(project, "SPEC.md", "# SPEC v2\n")
    git(project, "commit", "-qam", "T000")
    task = load_tasks(project / "TASKS.md").get("T001")
    errors = check_task(project, task, config, "HEAD")
    assert any("SPEC.md：冻结文件相对 skeleton-v1" in e for e in errors), errors


def test_cli_check(project, capsys):
    write(project, "src/lexer.py", SKELETON.replace("strict: bool", "strict: int"))
    assert main(["check", "T001", str(project)]) == 1
    assert main(["check", "T999", str(project)]) == 1
    write(project, "src/lexer.py", IMPLEMENTED)
    assert main(["check", "T001", str(project)]) == 0
    out = capsys.readouterr().out
    assert "修改了 tokenize 的签名" in out and "T999 不存在" in out and "[通过]" in out
