class CalcError(Exception):
    """计算器所有错误的基类。"""


class LexError(CalcError):
    """词法错误。"""


class ParseError(CalcError):
    """语法错误。"""


class EvalError(CalcError):
    """求值错误。"""
