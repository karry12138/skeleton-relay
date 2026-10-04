from .evaluator import evaluate
from .lexer import tokenize
from .parser import parse


def calc(source: str) -> float:
    """计算表达式字符串的值。"""
    return evaluate(parse(tokenize(source)))
