# TASKS

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
- src/calc/errors.py
instructions: |
  实现 src/calc/lexer.py 中的 tokenize(source: str) -> list[Token]。
  - 从左到右扫描，跳过空白字符（str.isspace()）。
  - 数字：读取一段连续的 数字和 "." 字符，记为 text。
    text 必须匹配正则 \d+(\.\d+)?，否则抛出 LexError(f"invalid number {text!r} at {pos}")，
    pos 为这段文本首字符的下标。例如 "3."、"1.2.3"、".5" 都是 invalid number。
    合法时产出 Token(TokenKind.NUMBER, text, pos)。
  - 单字符符号：+ - * / ( ) 分别产出 PLUS MINUS STAR SLASH LPAREN RPAREN，text 为该字符。
  - 其他字符抛出 LexError(f"unexpected character {ch!r} at {pos}")。
  - 最后追加 Token(TokenKind.EOF, "", len(source))。
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
- src/calc/errors.py
instructions: |
  实现 src/calc/parser.py 中的 parse(tokens: list[Token]) -> Expr，文法：
    expr    := term (("+" | "-") term)*
    term    := unary (("*" | "/") unary)*
    unary   := "-" unary | primary
    primary := NUMBER | "(" expr ")"
  - 可以新增以 _ 开头的私有辅助函数或私有类（例如 _Parser），不要新增公开符号。
  - NUMBER 产出 Num(float(token.text))；一元负号产出 Neg(operand)；
    二元运算产出 BinOp(op, left, right)，op 为 "+" "-" "*" "/"，同级左结合。
  - 解析完 expr 后当前 token 必须是 EOF，否则视为错误。
  - 任何错误都抛出 ParseError(f"unexpected {tok.kind.name} {tok.text!r} at {tok.pos}")，
    tok 为出错时的当前 token。例如 "1 +" 在 EOF 处报 "unexpected EOF '' at 2"。
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
- src/calc/errors.py
instructions: |
  实现 src/calc/evaluator.py 中的 evaluate(expr: Expr) -> float，用 match 语句分派：
  - Num(value) 返回 value；Neg(operand) 返回 -evaluate(operand)。
  - BinOp(op, left, right)：先求两侧的值，再按 op 计算 + - * /。
  - 除法时右侧值为 0 抛出 EvalError("division by zero")。
acceptance:
- tests/test_evaluator.py
- tests/test_end_to_end.py
status: todo
attempts: 0
last_error: null
```
