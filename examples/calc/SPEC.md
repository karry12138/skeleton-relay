# SPEC

## 1. 目标

四则运算表达式计算器：输入字符串，输出浮点结果。用于冒烟测试 skeleton-relay 流程。

## 2. 范围与约束

- 必须做到：整数与小数、`+ - * /`、括号、一元负号、错误定位。
- 明确不做：变量、函数调用、幂运算、科学计数法。
- 只用 Python 3.11 标准库。

## 3. 设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 解析算法 | 递归下降 | 文法小，易实现易测试 |
| 数值类型 | 一律 `float` | 简化求值 |
| 错误 | 统一继承 `CalcError` | 调用方可一次捕获 |

## 4. 模块与接口

| 文件 | 职责 | 公开接口 | 任务 |
|---|---|---|---|
| `src/calc/tokens.py` | Token 类型 | `TokenKind`、`Token` | 骨架已完成 |
| `src/calc/nodes.py` | 语法树节点 | `Num`、`Neg`、`BinOp`、`Expr` | 骨架已完成 |
| `src/calc/errors.py` | 异常 | `CalcError`、`LexError`、`ParseError`、`EvalError` | 骨架已完成 |
| `src/calc/lexer.py` | 词法分析 | `tokenize(source) -> list[Token]` | T001 |
| `src/calc/parser.py` | 语法分析 | `parse(tokens) -> Expr` | T002 |
| `src/calc/evaluator.py` | 求值 | `evaluate(expr) -> float` | T003 |
| `src/calc/__init__.py` | 入口 | `calc(source) -> float` | 骨架已完成 |

## 5. 数据结构

- `Token(kind, text, pos)`：`text` 为源码原文（EOF 为 `""`），`pos` 为该 token 首字符在源码中的下标（EOF 为 `len(source)`）。
- `Num(value: float)`、`Neg(operand: Expr)`、`BinOp(op: str, left: Expr, right: Expr)`，`op` 取 `"+" "-" "*" "/"`。
- 所有数据类均为 `frozen=True`，可直接用 `==` 比较。

## 6. 调用流程

`calc(source)` → `tokenize` → `parse` → `evaluate`。

### 文法

```
expr    := term (("+" | "-") term)*
term    := unary (("*" | "/") unary)*
unary   := "-" unary | primary
primary := NUMBER | "(" expr ")"
```

`parse` 必须消费到 EOF；`expr` 之后仍有剩余 token 视为错误。

## 7. 错误处理

| 场景 | 抛出位置 | 异常 | 消息格式 |
|---|---|---|---|
| 非法字符 | `tokenize` | `LexError` | `unexpected character {ch!r} at {pos}` |
| 数字格式错误（如 `3.`、`1.2.3`） | `tokenize` | `LexError` | `invalid number {text!r} at {pos}` |
| 不符合文法 | `parse` | `ParseError` | `unexpected {kind.name} {text!r} at {pos}` |
| 除数为 0 | `evaluate` | `EvalError` | `division by zero` |
