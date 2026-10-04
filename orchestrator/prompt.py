"""为执行模型生成单个任务的提示词。"""

from __future__ import annotations

from .tasks import Task


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- （无）"


def build_prompt(task: Task) -> str:
    sections = [
        f"# 任务 {task.id}：{task.title}",
        "你只负责实现这一个任务。骨架、规格和测试都已定稿，你的工作是把桩函数替换为真正的实现。",
        f"## 可以修改的文件\n{_bullets(task.files)}",
        f"## 只读参考（已在上下文中，禁止修改）\n{_bullets(task.read_only)}",
        f"## 实现要求\n{task.instructions.strip()}",
        "## 硬性约束\n"
        "1. 只修改「可以修改的文件」，不要创建、删除或修改其他任何文件（包括测试）。\n"
        "2. 不要修改已有函数、类、方法的签名（名称、参数、默认值、类型标注、装饰器），也不要删除它们。\n"
        "3. 不要新增公开符号；需要辅助函数或辅助类时，名称以 _ 开头。\n"
        '4. 把 raise NotImplementedError("...") 替换为真正的实现，不要留下 TODO。\n'
        "5. 直接给出代码修改，不需要额外解释。",
        f"## 验收\n以下测试必须全部通过：\n{_bullets(task.acceptance)}",
    ]
    if task.last_error:
        sections.append(
            "## 上一次尝试失败的原因\n"
            "代码已回滚到本任务开始前的状态。请避免以下问题：\n"
            f"```\n{task.last_error.strip()}\n```"
        )
    return "\n\n".join(sections) + "\n"
