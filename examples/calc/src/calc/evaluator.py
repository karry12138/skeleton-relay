from .errors import EvalError
from .nodes import BinOp, Expr, Neg, Num


def evaluate(expr: Expr) -> float:
    """计算语法树的值。

    Args:
        expr: `parse` 的输出。

    Returns:
        浮点结果。

    Raises:
        EvalError: 除数为 0。
    """
    raise NotImplementedError("T003")
