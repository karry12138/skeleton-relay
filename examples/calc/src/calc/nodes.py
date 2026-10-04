from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Num:
    value: float


@dataclass(frozen=True)
class Neg:
    operand: Expr


@dataclass(frozen=True)
class BinOp:
    op: str
    left: Expr
    right: Expr


Expr = Num | Neg | BinOp
