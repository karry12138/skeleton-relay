from dataclasses import dataclass
from enum import Enum


class TokenKind(Enum):
    NUMBER = "NUMBER"
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    LPAREN = "("
    RPAREN = ")"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    pos: int
