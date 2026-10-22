"""Static name validation and resolution (docs/spec.md, sections 6 and 7.1).

For each scope (module or function) the validator first collects every
declaration in it (blocks of IF/WHILE/FOR do not create scopes; FUNC bodies do),
then walks the statements in source order to check that every name is declared
before it is used. Function bodies are walked after their enclosing scope has
been walked completely, so they see later declarations of enclosing scopes (P7).

Every `Name` node is annotated with `hops`: the number of function scopes to go
up at run time, or `nodes.BUILTIN`. Errors are collected, not raised.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import nodes as n
from .builtins import BUILTINS
from .errors import FalaszError, FalaszNameError, Pos


@dataclass
class _Decl:
    kind: str  # "let", "func", "for", "param", "import"
    pos: Pos


@dataclass
class _Scope:
    parent: "_Scope | None"
    decls: dict[str, _Decl] = field(default_factory=dict)
    declared: set[str] = field(default_factory=set)  # declared so far in source order
    pending: list[n.Func] = field(default_factory=list)


class Validator:
    def __init__(self, path: str):
        self.path = path
        self.errors: list[FalaszError] = []

    def error(self, message: str, pos: Pos) -> None:
        self.errors.append(FalaszNameError(message, self.path, pos))

    # -------------------------------------------------------------- scopes

    def validate(self, program: n.Program) -> list[FalaszError]:
        module = _Scope(None)
        self.collect(program.body, module)
        self.walk_scope(program.body, module)
        self.check_exports(program.body, module)
        self.errors.sort(key=lambda e: e.pos)
        return self.errors

    def declare_static(self, scope: _Scope, name: str, kind: str, pos: Pos) -> None:
        if name in BUILTINS:
            self.error(f"'{name}' is a builtin name and cannot be redeclared", pos)
            return
        previous = scope.decls.get(name)
        if previous is None:
            scope.decls[name] = _Decl(kind, pos)
        elif not (kind == "for" and previous.kind == "for"):
            self.error(
                f"'{name}' is already declared in this scope (line {previous.pos.line})", pos
            )

    def collect(self, body: list[n.Stmt], scope: _Scope) -> None:
        """Declarations of one scope, in source order; does not enter FUNC bodies."""
        for stmt in body:
            match stmt:
                case n.Let(name=name, name_pos=pos):
                    self.declare_static(scope, name, "let", pos)
                case n.Func(name=name, name_pos=pos):
                    self.declare_static(scope, name, "func", pos)
                case n.For(var=var, var_pos=pos, body=inner):
                    self.declare_static(scope, var, "for", pos)
                    self.collect(inner, scope)
                case n.Import(binding_pos=pos):
                    self.declare_static(scope, stmt.binding, "import", pos)
                case n.If(then=then, otherwise=otherwise):
                    self.collect(then, scope)
                    if otherwise:
                        self.collect(otherwise, scope)
                case n.While(body=inner):
                    self.collect(inner, scope)

    def walk_scope(self, body: list[n.Stmt], scope: _Scope) -> None:
        self.block(body, scope)
        while scope.pending:
            func = scope.pending.pop(0)
            inner = _Scope(scope)
            for name, pos in func.params:
                self.declare_static(inner, name, "param", pos)
                inner.declared.add(name)
            self.collect(func.body, inner)
            self.walk_scope(func.body, inner)

    def check_exports(self, body: list[n.Stmt], module: _Scope) -> None:
        exported: dict[str, Pos] = {}
        for stmt in body:
            if isinstance(stmt, n.Export):
                for name, pos in stmt.names:
                    if name in exported:
                        self.error(f"'{name}' is already exported (line {exported[name].line})", pos)
                    elif name not in module.decls:
                        self.error(f"cannot export '{name}': it is not declared at the top level of this file", pos)
                    else:
                        exported[name] = pos

    # ---------------------------------------------------------- statements

    def block(self, body: list[n.Stmt], scope: _Scope) -> None:
        for stmt in body:
            self.statement(stmt, scope)

    def statement(self, stmt: n.Stmt, scope: _Scope) -> None:
        match stmt:
            case n.Let(name=name, value=value):
                self.expr(value, scope)
                scope.declared.add(name)
            case n.Func(name=name):
                scope.declared.add(name)
                scope.pending.append(stmt)
            case n.For(var=var, iterable=iterable, body=body):
                self.expr(iterable, scope)
                scope.declared.add(var)
                self.block(body, scope)
            case n.If(condition=cond, then=then, otherwise=otherwise):
                self.expr(cond, scope)
                self.block(then, scope)
                if otherwise:
                    self.block(otherwise, scope)
            case n.While(condition=cond, body=body):
                self.expr(cond, scope)
                self.block(body, scope)
            case n.Import():
                scope.declared.add(stmt.binding)
            case n.Assign(target=target, value=value):
                if isinstance(target, n.Name):
                    self.name(target, scope, assigning=True)
                else:
                    self.expr(target.target, scope)
                    self.expr(target.index, scope)
                self.expr(value, scope)
            case n.Say(value=value):
                self.expr(value, scope)
            case n.Return(value=value):
                if value is not None:
                    self.expr(value, scope)
            case n.ExprStmt(expr=expr):
                self.expr(expr, scope)
            case n.Export() | n.Break() | n.Continue():
                pass
            case _:
                raise AssertionError(f"unknown statement {stmt!r}")

    # --------------------------------------------------------- expressions

    def name(self, node: n.Name, scope: _Scope, assigning: bool = False) -> None:
        hops = 0
        s: _Scope | None = scope
        while s is not None:
            if node.name in s.decls:
                node.hops = hops
                if node.name not in s.declared:
                    self.error(f"'{node.name}' is used before its declaration "
                               f"(line {s.decls[node.name].pos.line})", node.pos)
                return
            s = s.parent
            hops += 1
        if node.name in BUILTINS:
            node.hops = n.BUILTIN
            if assigning:
                self.error(f"cannot assign to builtin '{node.name}'", node.pos)
            return
        self.error(f"'{node.name}' is not declared", node.pos)

    def expr(self, node: n.Expr, scope: _Scope) -> None:
        match node:
            case n.Name():
                self.name(node, scope)
            case n.Unary(operand=operand):
                self.expr(operand, scope)
            case n.Binary(left=left, right=right):
                self.expr(left, scope)
                self.expr(right, scope)
            case n.Call(callee=callee, args=args):
                self.expr(callee, scope)
                for arg in args:
                    self.expr(arg, scope)
            case n.Index(target=target, index=index):
                self.expr(target, scope)
                self.expr(index, scope)
            case n.Member(target=target):
                self.expr(target, scope)
            case n.ListLit(items=items):
                for item in items:
                    self.expr(item, scope)
            case n.MapLit(entries=entries):
                for key, value in entries:
                    self.expr(key, scope)
                    self.expr(value, scope)
            case n.IntLit() | n.FloatLit() | n.StrLit() | n.BoolLit() | n.NullLit():
                pass
            case _:
                raise AssertionError(f"unknown expression {node!r}")


def validate(program: n.Program) -> list[FalaszError]:
    return Validator(program.path).validate(program)
