import pytest

from calc.errors import ParseError
from calc.nodes import BinOp, Neg, Num
from calc.parser import parse
from calc.tokens import Token, TokenKind as K


def toks(*items):
    """用 (kind, text) 构造 token 列表，pos 依次编号，末尾自动加 EOF。"""
    tokens = [Token(kind, text, i) for i, (kind, text) in enumerate(items)]
    return tokens + [Token(K.EOF, "", len(items))]


N = lambda v: (K.NUMBER, v)
PLUS, MINUS, STAR, SLASH = (K.PLUS, "+"), (K.MINUS, "-"), (K.STAR, "*"), (K.SLASH, "/")
LP, RP = (K.LPAREN, "("), (K.RPAREN, ")")


def test_single_number():
    assert parse(toks(N("2.5"))) == Num(2.5)


def test_precedence():
    assert parse(toks(N("1"), PLUS, N("2"), STAR, N("3"))) == BinOp("+", Num(1.0), BinOp("*", Num(2.0), Num(3.0)))


def test_left_associative():
    assert parse(toks(N("8"), MINUS, N("3"), MINUS, N("2"))) == BinOp("-", BinOp("-", Num(8.0), Num(3.0)), Num(2.0))
    assert parse(toks(N("8"), SLASH, N("4"), STAR, N("2"))) == BinOp("*", BinOp("/", Num(8.0), Num(4.0)), Num(2.0))


def test_parentheses():
    assert parse(toks(LP, N("1"), PLUS, N("2"), RP, STAR, N("3"))) == BinOp(
        "*", BinOp("+", Num(1.0), Num(2.0)), Num(3.0)
    )


def test_unary_minus():
    assert parse(toks(MINUS, MINUS, N("1"))) == Neg(Neg(Num(1.0)))
    assert parse(toks(N("2"), STAR, MINUS, N("3"))) == BinOp("*", Num(2.0), Neg(Num(3.0)))


@pytest.mark.parametrize(
    "tokens, message",
    [
        (toks(N("1"), PLUS), r"^unexpected EOF '' at 2$"),
        (toks(LP, N("1")), r"^unexpected EOF '' at 2$"),
        (toks(N("1"), N("2")), r"^unexpected NUMBER '2' at 1$"),
        (toks(RP), r"^unexpected RPAREN '\)' at 0$"),
        (toks(), r"^unexpected EOF '' at 0$"),
    ],
)
def test_errors(tokens, message):
    with pytest.raises(ParseError, match=message):
        parse(tokens)
