"""Builtin functions RANGE, STR, INT, FLOAT, LEN, INPUT (docs/spec.md, section 8)."""

from __future__ import annotations

import re
import sys
from typing import Any

from .errors import FalaszArithmeticError, FalaszLimitError, FalaszTypeError, FalaszValueError
from .values import Builtin, FMap, is_number, quote, to_str, type_name

MAX_RANGE_LENGTH = 10_000_000

_INT_TEXT = re.compile(r"-?[0-9]+", re.ASCII)
_FLOAT_TEXT = re.compile(r"-?[0-9]+(\.[0-9]+)?", re.ASCII)


def _int_from_text(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise FalaszLimitError(
            f"text has too many digits to convert to INTEGER (limit {sys.get_int_max_str_digits()})"
        ) from None


def _range(interp, args: list[Any]) -> list[int]:
    for arg in args:
        if type(arg) is not int:
            raise FalaszTypeError(f"RANGE arguments must be INTEGER, not {type_name(arg)}")
    if len(args) == 3 and args[2] == 0:
        raise FalaszValueError("RANGE step must not be 0")
    r = range(*args)
    if len(r) > MAX_RANGE_LENGTH:
        raise FalaszLimitError(f"RANGE would have {len(r)} elements, limit is {MAX_RANGE_LENGTH}")
    return list(r)


def _str(interp, args: list[Any]) -> str:
    return to_str(args[0])


def _int(interp, args: list[Any]) -> int:
    (x,) = args
    t = type(x)
    if t is int:
        return x
    if t is float:
        return int(x)  # truncates toward zero; finite floats always convert
    if t is str:
        if not _INT_TEXT.fullmatch(x):
            raise FalaszValueError(f"cannot convert {quote(x)} to INTEGER")
        return _int_from_text(x)
    raise FalaszTypeError(f"cannot convert {type_name(x)} to INTEGER")


def _float(interp, args: list[Any]) -> float:
    (x,) = args
    if is_number(x):
        try:
            return float(x)
        except OverflowError:
            raise FalaszArithmeticError("INTEGER is too large for a FLOAT") from None
    if type(x) is str:
        if not _FLOAT_TEXT.fullmatch(x):
            raise FalaszValueError(f"cannot convert {quote(x)} to FLOAT")
        value = float(x)
        if value in (float("inf"), float("-inf")):
            raise FalaszArithmeticError("number is too large for a FLOAT")
        return value
    raise FalaszTypeError(f"cannot convert {type_name(x)} to FLOAT")


def _len(interp, args: list[Any]) -> int:
    (x,) = args
    if type(x) in (str, list, FMap):
        return len(x)
    raise FalaszTypeError(f"LEN expects STRING, LIST or MAP, not {type_name(x)}")


def _input(interp, args: list[Any]) -> str | None:
    if args:
        if type(args[0]) is not str:
            raise FalaszTypeError(f"INPUT prompt must be STRING, not {type_name(args[0])}")
        interp.out.write(args[0])
    interp.out.flush()
    return interp.read_line()


BUILTINS: dict[str, Builtin] = {
    b.name: b
    for b in [
        Builtin("RANGE", 2, 3, _range),
        Builtin("STR", 1, 1, _str),
        Builtin("INT", 1, 1, _int),
        Builtin("FLOAT", 1, 1, _float),
        Builtin("LEN", 1, 1, _len),
        Builtin("INPUT", 0, 1, _input),
    ]
}
