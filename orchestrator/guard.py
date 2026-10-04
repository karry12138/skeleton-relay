"""任务完成后的接口保护检查。

- 整文件冻结：read_only 与 protected 中的文件相对骨架 tag 不得有任何改动。
- 越界修改：相对任务开始前的提交，只允许 files 中的文件发生变化。
- 签名冻结：files 中的 .py 文件，骨架里已有的符号签名不得改动或删除，不得新增公开符号。
"""

from __future__ import annotations

import ast
import fnmatch
import subprocess
from pathlib import Path

from .config import RelayConfig
from .tasks import Task


class GitError(RuntimeError):
    pass


def run_git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=off", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} 失败：{proc.stderr.strip()}")
    return proc.stdout


def _norm(path: str) -> str:
    return path.replace("\\", "/").removeprefix("./")


def changed_files(root: Path, ref: str) -> set[str]:
    """工作区（含未跟踪文件）相对 ref 发生变化的文件。"""
    tracked = run_git(root, "diff", "--name-only", ref, "--").splitlines()
    untracked = run_git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    return {_norm(p) for p in tracked + untracked if p}


def file_at(root: Path, ref: str, path: str) -> str | None:
    try:
        return run_git(root, "show", f"{ref}:{_norm(path)}")
    except GitError:
        return None


def _decorators(node) -> str:
    return "".join(f"@{ast.unparse(d)} " for d in node.decorator_list)


def _function_sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{_decorators(node)}{prefix} {node.name}({ast.unparse(node.args)}){returns}"


def _class_sig(node: ast.ClassDef) -> str:
    bases = [ast.unparse(b) for b in node.bases] + [ast.unparse(k) for k in node.keywords]
    return f"{_decorators(node)}class {node.name}({', '.join(bases)})"


def _collect(body: list[ast.stmt], prefix: str, out: dict[str, str]) -> None:
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[prefix + node.name] = _function_sig(node)
        elif isinstance(node, ast.ClassDef):
            name = prefix + node.name
            out[name] = _class_sig(node)
            _collect(node.body, name + ".", out)
        elif prefix and isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            value = f" = {ast.unparse(node.value)}" if node.value else ""
            out[prefix + node.target.id] = f"{node.target.id}: {ast.unparse(node.annotation)}{value}"


def signatures(source: str) -> dict[str, str]:
    """模块级与类内（递归）函数、类、类字段的签名；函数体内部的定义不计入。"""
    out: dict[str, str] = {}
    _collect(ast.parse(source).body, "", out)
    return out


def _is_public(qualname: str) -> bool:
    return not any(part.startswith("_") for part in qualname.split("."))


def compare_signatures(path: str, baseline: str, current: str) -> list[str]:
    try:
        after = signatures(current)
    except SyntaxError as exc:
        return [f"{path}：语法错误（第 {exc.lineno} 行）：{exc.msg}"]
    before = signatures(baseline)
    errors = []
    for name, sig in before.items():
        if name not in after:
            errors.append(f"{path}：删除了骨架符号 {name}")
        elif after[name] != sig:
            errors.append(f"{path}：修改了 {name} 的签名\n    骨架：{sig}\n    现在：{after[name]}")
    for name in after.keys() - before.keys():
        if _is_public(name):
            errors.append(f"{path}：新增了公开符号 {name}（只允许新增 _ 开头的私有符号）")
    return errors


def _matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, _norm(p)) for p in patterns)


def check_task(root: str | Path, task: Task, config: RelayConfig, base_ref: str) -> list[str]:
    """返回违规列表；为空表示通过。base_ref 是该任务开始前的提交。"""
    root = Path(root)
    tag = config.skeleton_tag
    allowed = {_norm(p) for p in task.files}
    frozen = [*task.read_only, *config.protected]
    errors = []

    for path in sorted(changed_files(root, tag)):
        if _matches(path, frozen):
            errors.append(f"{path}：冻结文件相对 {tag} 被改动")

    ignored = {_norm(config.tasks_file)}
    for path in sorted(changed_files(root, base_ref) - allowed - ignored):
        if not _matches(path, frozen):
            errors.append(f"{path}：不在任务 {task.id} 的 files 中，不允许修改")

    for path in sorted(allowed):
        if not path.endswith(".py"):
            continue
        baseline = file_at(root, tag, path)
        if baseline is None:
            continue
        target = root / path
        if not target.exists():
            errors.append(f"{path}：骨架文件被删除")
            continue
        errors.extend(compare_signatures(path, baseline, target.read_text(encoding="utf-8")))
    return errors
