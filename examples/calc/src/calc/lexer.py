from .errors import LexError
from .tokens import Token, TokenKind


def tokenize(source: str) -> list[Token]:
    """把源码切分为 token 列表，末尾总有一个 EOF token。

    Args:
        source: 表达式源码。

    Returns:
        按出现顺序排列的 token；空白不产出 token。

    Raises:
        LexError: 遇到非法字符或格式错误的数字。
    """
    raise NotImplementedError("T001")
