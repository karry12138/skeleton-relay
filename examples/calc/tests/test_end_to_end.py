import pytest

from calc import calc
from calc.errors import CalcError


@pytest.mark.parametrize(
    "source, expected",
    [
        ("1 + 2 * 3", 7.0),
        ("(1 + 2) * 3", 9.0),
        ("-2 * -3", 6.0),
        ("10 / 4", 2.5),
        ("2 - 3 - 4", -5.0),
        ("-(1.5 + 0.5) * (8 / (3 - 1))", -8.0),
    ],
)
def test_calc(source, expected):
    assert calc(source) == expected


@pytest.mark.parametrize("source", ["1 / 0", "1 +", "2 $ 3", "(1"])
def test_errors_are_calc_errors(source):
    with pytest.raises(CalcError):
        calc(source)
