from .errors import ParseError
from .nodes import BinOp, Expr, Neg, Num
from .tokens import Token, TokenKind


def parse(tokens: list[Token]) -> Expr:
    """按 SPEC.md 的文法把 token 列表解析为语法树。

    Args:
        tokens: `tokenize` 的输出，以 EOF 结尾。

    Returns:
        表达式语法树。

    Raises:
        ParseError: token 序列不符合文法，或 expr 之后仍有剩余 token。
    """
    raise NotImplementedError("T002")
