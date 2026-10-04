import pytest

from calc.errors import EvalError
from calc.evaluator import evaluate
from calc.nodes import BinOp, Neg, Num


def test_num():
    assert evaluate(Num(2.5)) == 2.5


def test_operators():
    assert evaluate(BinOp("+", Num(1.0), Num(2.0))) == 3.0
    assert evaluate(BinOp("-", Num(1.0), Num(2.0))) == -1.0
    assert evaluate(BinOp("*", Num(3.0), Num(4.0))) == 12.0
    assert evaluate(BinOp("/", Num(1.0), Num(4.0))) == 0.25


def test_nested_and_neg():
    assert evaluate(Neg(BinOp("*", Num(2.0), Neg(Num(3.0))))) == 6.0


def test_division_by_zero():
    with pytest.raises(EvalError, match=r"^division by zero$"):
        evaluate(BinOp("/", Num(1.0), BinOp("-", Num(2.0), Num(2.0))))
