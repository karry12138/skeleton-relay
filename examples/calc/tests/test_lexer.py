import pytest

from calc.errors import LexError
from calc.lexer import tokenize
from calc.tokens import Token, TokenKind as K


def test_numbers_and_operator():
    assert tokenize("1 + 2.5") == [
        Token(K.NUMBER, "1", 0),
        Token(K.PLUS, "+", 2),
        Token(K.NUMBER, "2.5", 4),
        Token(K.EOF, "", 7),
    ]


def test_all_symbols_without_spaces():
    kinds = [t.kind for t in tokenize("(1-2)*3/4")]
    assert kinds == [K.LPAREN, K.NUMBER, K.MINUS, K.NUMBER, K.RPAREN, K.STAR, K.NUMBER, K.SLASH, K.NUMBER, K.EOF]


def test_multi_digit_and_whitespace():
    assert tokenize("  12.75\t\n") == [Token(K.NUMBER, "12.75", 2), Token(K.EOF, "", 9)]


def test_empty_source():
    assert tokenize("") == [Token(K.EOF, "", 0)]


def test_illegal_character():
    with pytest.raises(LexError, match=r"^unexpected character '&' at 2$"):
        tokenize("1 & 2")


@pytest.mark.parametrize("source, text", [("3.", "3."), ("1.2.3", "1.2.3"), (".5", ".5")])
def test_invalid_number(source, text):
    with pytest.raises(LexError, match=rf"^invalid number '{text}' at 0$"):
        tokenize(source)
