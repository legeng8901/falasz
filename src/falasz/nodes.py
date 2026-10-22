"""AST node definitions (docs/spec.md, section 3).

Every node carries `pos`, the location diagnostics point at (spec section 11.1):
operators and postfix operations use their operator token, statements use their
keyword, names use the name itself. `start()` gives the first token of an
expression, used e.g. for non-BOOLEAN conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

from .errors import Pos


class Node:
    pos: Pos


# ---------------------------------------------------------------- expressions


class Expr(Node):
    pass


@dataclass(slots=True)
class IntLit(Expr):
    value: int
    pos: Pos


@dataclass(slots=True)
class FloatLit(Expr):
    value: float
    pos: Pos


@dataclass(slots=True)
class StrLit(Expr):
    value: str
    pos: Pos


@dataclass(slots=True)
class BoolLit(Expr):
    value: bool
    pos: Pos


@dataclass(slots=True)
class NullLit(Expr):
    pos: Pos


BUILTIN = -1  # Name.hops for names of the builtin scope


@dataclass(slots=True)
class Name(Expr):
    name: str
    pos: Pos
    # Set by the validator: how many function scopes to go up to reach the
    # declaring scope (0 = current), or BUILTIN. None = not resolved yet.
    hops: int | None = None


@dataclass(slots=True)
class ListLit(Expr):
    items: list[Expr]
    pos: Pos  # '['


@dataclass(slots=True)
class MapLit(Expr):
    entries: list[tuple[Expr, Expr]]
    pos: Pos  # '{'


@dataclass(slots=True)
class Unary(Expr):
    op: str  # "-" or "NOT"
    operand: Expr
    pos: Pos  # operator token


@dataclass(slots=True)
class Binary(Expr):
    op: str  # "+", "==", "AND", ...
    left: Expr
    right: Expr
    pos: Pos  # operator token


@dataclass(slots=True)
class Call(Expr):
    callee: Expr
    args: list[Expr]
    pos: Pos  # '('


@dataclass(slots=True)
class Index(Expr):
    target: Expr
    index: Expr
    pos: Pos  # '['


@dataclass(slots=True)
class Member(Expr):
    target: Expr
    name: str
    pos: Pos  # '.'
    name_pos: Pos


def start(expr: Expr) -> Pos:
    """Position of the first token of an expression.

    Parentheses are not kept in the AST, so for `(a + b) * c` this is `a`.
    """
    while isinstance(expr, (Binary, Call, Index, Member)):
        expr = expr.left if isinstance(expr, Binary) else expr.callee if isinstance(expr, Call) else expr.target
    return expr.pos


# ----------------------------------------------------------------- statements


class Stmt(Node):
    pass


@dataclass(slots=True)
class Import(Stmt):
    module: str
    local: bool
    alias: str | None
    pos: Pos  # IMPORT keyword: resolution errors (missing file, cycle)
    binding_pos: Pos  # alias if present, else module name: declaration errors
    # Set by the module loader: "std:<name>" or the canonical path of the file.
    resolved: str | None = None

    @property
    def binding(self) -> str:
        return self.alias if self.alias is not None else self.module


@dataclass(slots=True)
class Export(Stmt):
    names: list[tuple[str, Pos]]
    pos: Pos


@dataclass(slots=True)
class Let(Stmt):
    name: str
    value: Expr
    pos: Pos  # LET keyword
    name_pos: Pos


@dataclass(slots=True)
class Func(Stmt):
    name: str
    params: list[tuple[str, Pos]]
    body: list[Stmt]
    pos: Pos  # FUNC keyword
    name_pos: Pos


@dataclass(slots=True)
class If(Stmt):
    condition: Expr
    then: list[Stmt]
    otherwise: list[Stmt] | None  # ELSE IF is a single nested If
    pos: Pos


@dataclass(slots=True)
class While(Stmt):
    condition: Expr
    body: list[Stmt]
    pos: Pos


@dataclass(slots=True)
class For(Stmt):
    var: str
    iterable: Expr
    body: list[Stmt]
    pos: Pos
    var_pos: Pos


@dataclass(slots=True)
class Say(Stmt):
    value: Expr
    pos: Pos


@dataclass(slots=True)
class Return(Stmt):
    value: Expr | None
    pos: Pos


@dataclass(slots=True)
class Break(Stmt):
    pos: Pos


@dataclass(slots=True)
class Continue(Stmt):
    pos: Pos


@dataclass(slots=True)
class Assign(Stmt):
    target: Name | Index
    value: Expr
    pos: Pos  # '='


@dataclass(slots=True)
class ExprStmt(Stmt):
    expr: Call
    pos: Pos


@dataclass(slots=True)
class Program(Node):
    body: list[Stmt]
    path: str
    pos: Pos = Pos(1, 1)


# ---------------------------------------------------------------- debugging


def dump(node: object) -> str:
    """Compact S-expression rendering of an AST, without positions (for tests/debugging)."""
    if isinstance(node, list):
        return "[" + " ".join(dump(n) for n in node) + "]"
    if isinstance(node, tuple):
        return "(" + " ".join(dump(n) for n in node if not isinstance(n, Pos)) + ")"
    match node:
        case IntLit(value=v) | FloatLit(value=v):
            return repr(v)
        case StrLit(value=v):
            return '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
        case BoolLit(value=v):
            return "TRUE" if v else "FALSE"
        case NullLit():
            return "NULL"
        case Name(name=n):
            return n
        case Unary(op=op, operand=a):
            return f"({op} {dump(a)})"
        case Binary(op=op, left=a, right=b):
            return f"({op} {dump(a)} {dump(b)})"
        case Node():
            parts = [type(node).__name__]
            for f in fields(node):  # type: ignore[arg-type]
                if f.name in ("pos", "name_pos", "var_pos", "binding_pos", "path", "resolved"):
                    continue
                value = getattr(node, f.name)
                parts.append(dump(value) if not isinstance(value, (str, bool)) and value is not None
                             else repr(value) if isinstance(value, str) else str(value))
            return "(" + " ".join(parts) + ")"
    return repr(node)
