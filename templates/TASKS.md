# TASKS

<!--
skeleton-relay 任务清单。每个任务 = 一个二级标题 + 一个 ```yaml task 代码块。
代码块之外的文字只给人看；编排器只读写代码块，并会回写 status / attempts / last_error。

字段：
  id            必填  唯一标识，如 T001
  title         必填  一句话标题
  depends_on    可选  前置任务 id 列表；全部 done 后本任务才会执行
  files         必填  允许修改的文件（相对项目根，/ 分隔）。只能改函数体，公开签名冻结
  read_only     可选  只读参考文件（SPEC.md、接口/类型定义、相关模块）。整文件冻结
  instructions  必填  实现要点。执行模型只能看到 files + read_only + 这段文字，必须自洽完整
  acceptance    必填  验收测试的 pytest 节点 id；全部通过才算 done
  status        编排器维护  todo / done / blocked
  attempts      编排器维护  已尝试次数
  last_error    编排器维护  最近一次失败原因
-->

## T001 词法分析

```yaml task
id: T001
title: 实现 tokenize
depends_on: []
files:
- src/calc/lexer.py
read_only:
- SPEC.md
- src/calc/tokens.py
instructions: |
  实现 tokenize(source: str) -> list[Token]。
  - 跳过空白；整数和小数都产出 Token(kind=TokenKind.NUMBER, text=原文)。
  - + - * / ( ) 分别对应 TokenKind 中同名成员。
  - 末尾追加一个 Token(kind=TokenKind.EOF, text="")。
  - 遇到其他字符抛出 LexError，消息包含该字符及其下标。
acceptance:
- tests/test_lexer.py
status: todo
attempts: 0
last_error: null
```

## T002 语法分析

```yaml task
id: T002
title: 实现递归下降 parse
depends_on:
- T001
files:
- src/calc/parser.py
read_only:
- SPEC.md
- src/calc/tokens.py
- src/calc/nodes.py
instructions: |
  实现 parse(tokens: list[Token]) -> Expr，文法见 SPEC.md「文法」一节。
  - * / 优先级高于 + -，同级左结合；支持一元负号与括号。
  - 不符合文法时抛出 ParseError，消息包含出错 Token 的 text。
acceptance:
- tests/test_parser.py
status: todo
attempts: 0
last_error: null
```

## T003 求值

```yaml task
id: T003
title: 实现 evaluate
depends_on:
- T002
files:
- src/calc/evaluator.py
read_only:
- SPEC.md
- src/calc/nodes.py
instructions: |
  实现 evaluate(expr: Expr) -> float，对 nodes.py 中每种节点做 match 分派。
  - 除数为 0 时抛出 EvalError("division by zero")。
acceptance:
- tests/test_evaluator.py
- tests/test_end_to_end.py::test_calc
status: todo
attempts: 0
last_error: null
```
