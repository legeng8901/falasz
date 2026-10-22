"""Runtime values and the operations defined on them (docs/spec.md, section 5).

Falasz values map onto Python objects:
    INTEGER -> int      FLOAT -> float     STRING -> str     BOOLEAN -> bool
    NULL -> None        LIST -> list       MAP -> FMap
    FUNCTION -> Builtin (implemented in Python) or Function (FUNC in Falasz)
    MODULE -> Module
Python's bool is a subclass of int, so type checks always use `type(v) is ...`.

Operations raise Falasz errors without a location; the interpreter attaches the
location of the operator or call that triggered them.
"""

from __future__ import annotations

import math
import sys
from decimal import Decimal
from typing import Any, Callable

from .errors import (
    FalaszArithmeticError,
    FalaszError,
    FalaszLimitError,
    FalaszTypeError,
    FalaszZeroDivisionError,
)

MAX_VALUE_DEPTH = 500


class FMap:
    """Insertion-ordered map. Keys are normalized so that TRUE and 1 stay distinct."""

    __slots__ = ("data",)

    def __init__(self) -> None:
        self.data: dict[tuple[bool, Any], Any] = {}

    @staticmethod
    def norm(key: Any) -> tuple[bool, Any]:
        if type(key) not in (int, str, bool):
            raise FalaszTypeError(f"map keys must be INTEGER, STRING or BOOLEAN, not {type_name(key)}")
        return (type(key) is bool, key)

    def get(self, key: Any, default: Any = None) -> Any:
        return self.data.get(self.norm(key), default)

    def __contains__(self, key: Any) -> bool:
        return self.norm(key) in self.data

    def __setitem__(self, key: Any, value: Any) -> None:
        self.data[self.norm(key)] = value

    def __len__(self) -> int:
        return len(self.data)

    def keys(self) -> list[Any]:
        return [k for _, k in self.data]

    def items(self) -> list[tuple[Any, Any]]:
        return [(k, v) for (_, k), v in self.data.items()]


class Builtin:
    """A function implemented by the interpreter. `fn(interpreter, args)`."""

    __slots__ = ("name", "min_args", "max_args", "fn")

    def __init__(self, name: str, min_args: int, max_args: int, fn: Callable):
        self.name = name
        self.min_args = min_args
        self.max_args = max_args
        self.fn = fn


class Function:
    """A user function: FUNC statement + the scope it was executed in (closure)."""

    __slots__ = ("name", "params", "body", "closure", "path")

    def __init__(self, name: str, params: list[str], body: list, closure: Any, path: str):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.path = path


class Module:
    """An imported module: its top-level scope and the names it exports."""

    __slots__ = ("name", "path", "scope", "exports")

    def __init__(self, name: str, path: str, scope: Any, exports: frozenset[str]):
        self.name = name
        self.path = path
        self.scope = scope
        self.exports = exports


# --------------------------------------------------------------------- types


def type_name(v: Any) -> str:
    t = type(v)
    if t is bool:
        return "BOOLEAN"
    if t is int:
        return "INTEGER"
    if t is float:
        return "FLOAT"
    if t is str:
        return "STRING"
    if v is None:
        return "NULL"
    if t is list:
        return "LIST"
    if t is FMap:
        return "MAP"
    if t is Builtin or t is Function:
        return "FUNCTION"
    if t is Module:
        return "MODULE"
    raise AssertionError(f"not a Falasz value: {v!r}")


def is_number(v: Any) -> bool:
    return type(v) is int or type(v) is float


# ---------------------------------------------------------- representation


def format_float(x: float) -> str:
    """Shortest round-tripping decimal form, always with a '.', never an exponent."""
    text = repr(x)
    if "e" in text or "E" in text:
        text = format(Decimal(text), "f")
    if "." not in text:
        text += ".0"
    return text


def format_int(x: int) -> str:
    try:
        return str(x)
    except ValueError:
        raise FalaszLimitError(
            f"integer has too many digits to convert to text (limit {sys.get_int_max_str_digits()})"
        ) from None


def quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'


def to_str(v: Any) -> str:
    """STR(v) / SAY v (spec section 5)."""
    if type(v) is str:
        return v
    parts: list[str] = []
    _repr(v, parts, set(), 0)
    return "".join(parts)


def _repr(v: Any, out: list[str], active: set[int], depth: int) -> None:
    t = type(v)
    if t is str:
        out.append(quote(v))
    elif t is bool:
        out.append("TRUE" if v else "FALSE")
    elif t is int:
        out.append(format_int(v))
    elif t is float:
        out.append(format_float(v))
    elif v is None:
        out.append("NULL")
    elif t is Builtin:
        out.append(f"<builtin {v.name}>")
    elif t is Function:
        out.append(f"<func {v.name}>")
    elif t is Module:
        out.append(f"<module {v.name}>")
    elif t is list or t is FMap:
        if id(v) in active:
            out.append("[...]" if t is list else "{...}")
            return
        if depth >= MAX_VALUE_DEPTH:
            raise FalaszLimitError(f"value is nested too deeply to convert to text (limit {MAX_VALUE_DEPTH})")
        active.add(id(v))
        if t is list:
            out.append("[")
            for i, item in enumerate(v):
                if i:
                    out.append(", ")
                _repr(item, out, active, depth + 1)
            out.append("]")
        else:
            out.append("{")
            for i, (key, item) in enumerate(v.items()):
                if i:
                    out.append(", ")
                _repr(key, out, active, depth + 1)
                out.append(": ")
                _repr(item, out, active, depth + 1)
            out.append("}")
        active.discard(id(v))
    else:
        raise AssertionError(f"not a Falasz value: {v!r}")


def show(v: Any) -> str:
    """Like STR, but strings are quoted (used in diagnostics)."""
    parts: list[str] = []
    _repr(v, parts, set(), 0)
    return "".join(parts)


# ------------------------------------------------------------------ equality


def equals(a: Any, b: Any) -> bool:
    return _equals(a, b, set(), 0)


def _equals(a: Any, b: Any, assumed: set[tuple[int, int]], depth: int) -> bool:
    if is_number(a) and is_number(b):
        return a == b
    ta = type(a)
    if ta is not type(b):
        return False
    if ta is list or ta is FMap:
        if a is b:
            return True
        if len(a) != len(b):
            return False
        pair = (id(a), id(b))
        if pair in assumed:  # cyclic structures: assume equal while comparing (coinduction)
            return True
        if depth >= MAX_VALUE_DEPTH:
            raise FalaszLimitError(f"values are nested too deeply to compare (limit {MAX_VALUE_DEPTH})")
        assumed.add(pair)
        if ta is list:
            return all(_equals(x, y, assumed, depth + 1) for x, y in zip(a, b))
        if a.data.keys() != b.data.keys():
            return False
        return all(_equals(a.data[k], b.data[k], assumed, depth + 1) for k in a.data)
    if ta is Builtin or ta is Function or ta is Module:
        return a is b
    return a == b


# --------------------------------------------------------------- arithmetic


def _finite(x: float) -> float:
    if math.isinf(x) or math.isnan(x):
        raise FalaszArithmeticError("FLOAT result is out of range")
    return x


def _float_op(fn: Callable[[], float]) -> float:
    try:
        return _finite(fn())
    except OverflowError:
        raise FalaszArithmeticError("number is too large for a FLOAT") from None


def _type_error(op: str, a: Any, b: Any) -> FalaszError:
    return FalaszTypeError(f"unsupported operand types for {op}: {type_name(a)} and {type_name(b)}")


def add(a: Any, b: Any) -> Any:
    ta, tb = type(a), type(b)
    if ta is int and tb is int:
        return a + b
    if is_number(a) and is_number(b):
        return _float_op(lambda: a + b)
    if ta is str and tb is str:
        return a + b
    if ta is list and tb is list:
        return a + b
    raise _type_error("+", a, b)


def _numeric(op: str, a: Any, b: Any) -> None:
    if not (is_number(a) and is_number(b)):
        raise _type_error(op, a, b)


def sub(a: Any, b: Any) -> Any:
    _numeric("-", a, b)
    if type(a) is int and type(b) is int:
        return a - b
    return _float_op(lambda: a - b)


def mul(a: Any, b: Any) -> Any:
    _numeric("*", a, b)
    if type(a) is int and type(b) is int:
        return a * b
    return _float_op(lambda: a * b)


def div(a: Any, b: Any) -> float:
    _numeric("/", a, b)
    if b == 0:
        raise FalaszZeroDivisionError("division by zero")
    return _float_op(lambda: a / b)


def mod(a: Any, b: Any) -> Any:
    _numeric("%", a, b)
    if b == 0:
        raise FalaszZeroDivisionError("modulo by zero")
    if type(a) is int and type(b) is int:
        return a % b
    return _float_op(lambda: a % b)


def neg(a: Any) -> Any:
    if not is_number(a):
        raise FalaszTypeError(f"unsupported operand type for unary -: {type_name(a)}")
    return -a


def compare(op: str, a: Any, b: Any) -> bool:
    if not ((is_number(a) and is_number(b)) or (type(a) is str and type(b) is str)):
        raise FalaszTypeError(f"cannot compare {type_name(a)} and {type_name(b)} with {op}")
    match op:
        case "<":
            return a < b
        case ">":
            return a > b
        case "<=":
            return a <= b
        case ">=":
            return a >= b
    raise AssertionError(op)


BINARY = {"+": add, "-": sub, "*": mul, "/": div, "%": mod}
COMPARISON = {"<", ">", "<=", ">="}
