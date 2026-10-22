"""Tree-walking interpreter (docs/spec.md, sections 5-8).

Implemented: literals, variables, expressions, SAY, IF/WHILE/FOR, BREAK/CONTINUE,
builtin and user functions (closures, recursion with a depth limit, call-stack
traces). Modules (stage 5) are reported as FalaszNotImplementedError.

The program must have been validated first: `Name.hops` tells which scope a
name lives in, so a variable whose declaration was not executed is reported as
missing instead of resolving to an outer variable of the same name (N2).
"""

from __future__ import annotations

import sys
from typing import Any, BinaryIO, TextIO

from . import nodes as n
from . import values as v
from .builtins import BUILTINS
from .errors import (
    FalaszArityError,
    FalaszError,
    FalaszIndexError,
    FalaszKeyError,
    FalaszLimitError,
    FalaszNameError,
    FalaszRecursionLimitError,
    FalaszTypeError,
    FalaszValueError,
    Pos,
    TraceEntry,
)

MAX_CALL_DEPTH = 500

FalaszNotImplementedError = type(
    "FalaszNotImplementedError", (FalaszError,), {"category": "NotImplementedError"}
)


class Scope:
    __slots__ = ("vars", "parent")

    def __init__(self, parent: Scope | None):
        self.vars: dict[str, Any] = {}
        self.parent = parent


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Return(Exception):
    __slots__ = ("value",)

    def __init__(self, value: Any):
        self.value = value


class Frame:
    """One active call: frame name ("<main>" or the function name) and its file."""

    __slots__ = ("name", "path")

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path


class Interpreter:
    def __init__(
        self,
        path: str,
        out: TextIO | None = None,
        inp: BinaryIO | None = None,
        max_steps: int | None = None,
        max_depth: int = MAX_CALL_DEPTH,
    ):
        self.path = path
        self.out = out if out is not None else sys.stdout
        self.inp = inp
        self.max_steps = max_steps
        self.max_depth = max_depth
        self.steps = 0
        self.frames = [Frame("<main>", path)]

    # ------------------------------------------------------------ helpers

    def located(self, err: FalaszError, pos: Pos) -> FalaszError:
        """Attach a location to an error raised by a value operation or builtin."""
        if err.pos is None:
            err.path, err.pos = self.path, pos
        return err

    def error(self, cls: type[FalaszError], message: str, pos: Pos) -> FalaszError:
        return cls(message, self.path, pos)

    def step(self, pos: Pos) -> None:
        self.steps += 1
        if self.max_steps is not None and self.steps > self.max_steps:
            raise self.error(FalaszLimitError, f"step limit of {self.max_steps} exceeded", pos)

    def boolean(self, expr: n.Expr, scope: Scope, what: str) -> bool:
        value = self.evaluate(expr, scope)
        if type(value) is not bool:
            raise self.error(FalaszTypeError, f"{what} must be BOOLEAN, not {v.type_name(value)}",
                             n.start(expr))
        return value

    def read_line(self) -> str | None:
        """One line of standard input for INPUT(); None at end of input."""
        if self.inp is None:
            return None
        data = self.inp.readline()
        if not data:
            return None
        if data.endswith(b"\n"):
            data = data[:-1]
            if data.endswith(b"\r"):
                data = data[:-1]
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise FalaszValueError("standard input is not valid UTF-8") from None

    # --------------------------------------------------------- statements

    def run(self, program: n.Program) -> None:
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 20_000))
        try:
            self.block(program.body, Scope(None))
        finally:
            sys.setrecursionlimit(old_limit)

    def block(self, body: list[n.Stmt], scope: Scope) -> None:
        for stmt in body:
            self.step(stmt.pos)
            self.statement(stmt, scope)

    def statement(self, stmt: n.Stmt, scope: Scope) -> None:
        match stmt:
            case n.Say(value=value):
                result = self.evaluate(value, scope)
                self.out.write(self.wrap(lambda: v.to_str(result), stmt.pos) + "\n")
            case n.Let(name=name, value=value):
                scope.vars[name] = self.evaluate(value, scope)
            # Assignment evaluates the right-hand side first, then the target (E7).
            case n.Assign(target=n.Name() as target, value=value):
                result = self.evaluate(value, scope)
                self.owner(target, scope).vars[target.name] = result
            case n.Assign(target=n.Index() as target, value=value):
                result = self.evaluate(value, scope)
                container = self.evaluate(target.target, scope)
                index = self.evaluate(target.index, scope)
                self.set_index(container, index, result, target.pos)
            case n.If(condition=cond, then=then, otherwise=otherwise):
                if self.boolean(cond, scope, "IF condition"):
                    self.block(then, scope)
                elif otherwise is not None:
                    self.block(otherwise, scope)
            case n.While(condition=cond, body=body):
                while self.boolean(cond, scope, "WHILE condition"):
                    try:
                        self.block(body, scope)
                    except _Break:
                        break
                    except _Continue:
                        pass
                    self.step(stmt.pos)
            case n.For(var=var, iterable=iterable, body=body):
                for item in self.iterate(self.evaluate(iterable, scope), n.start(iterable)):
                    scope.vars[var] = item
                    try:
                        self.block(body, scope)
                    except _Break:
                        break
                    except _Continue:
                        pass
                    self.step(stmt.pos)
            case n.Break():
                raise _Break
            case n.Continue():
                raise _Continue
            case n.ExprStmt(expr=expr):
                self.evaluate(expr, scope)
            case n.Export():
                pass  # checked statically; exports are read by importers (stage 5)
            case n.Func(name=name, params=params, body=body):
                scope.vars[name] = v.Function(name, [p for p, _ in params], body, scope, self.path)
            case n.Return(value=value):
                raise _Return(None if value is None else self.evaluate(value, scope))
            case n.Import():
                raise self.error(FalaszNotImplementedError, "IMPORT is not implemented yet (stage 5)", stmt.pos)
            case _:
                raise AssertionError(f"unexpected statement {stmt!r}")

    def iterate(self, value: Any, pos: Pos) -> list[Any] | str:
        t = type(value)
        if t is list:
            return list(value)  # snapshot
        if t is str:
            return value
        if t is v.FMap:
            return value.keys()  # snapshot
        raise self.error(FalaszTypeError, f"cannot iterate over {v.type_name(value)}", pos)

    # -------------------------------------------------------------- names

    def owner(self, node: n.Name, scope: Scope) -> Scope:
        """The scope holding `node`; raises NameError if its declaration has not run."""
        hops = node.hops
        assert hops is not None and hops != n.BUILTIN, f"unresolved name {node.name}"
        target = scope
        for _ in range(hops):
            target = target.parent  # type: ignore[assignment]
        if node.name not in target.vars:
            raise self.error(
                FalaszNameError,
                f"variable '{node.name}' does not exist: its declaration was not executed",
                node.pos,
            )
        return target

    def lookup(self, node: n.Name, scope: Scope) -> Any:
        if node.hops == n.BUILTIN:
            return BUILTINS[node.name]
        return self.owner(node, scope).vars[node.name]

    # -------------------------------------------------------- expressions

    def evaluate(self, node: n.Expr, scope: Scope) -> Any:
        match node:
            case n.IntLit(value=value) | n.FloatLit(value=value) | n.StrLit(value=value) | n.BoolLit(value=value):
                return value
            case n.NullLit():
                return None
            case n.Name():
                return self.lookup(node, scope)
            case n.Binary(op="AND", left=left, right=right):
                return self.boolean(left, scope, "operand of AND") and self.boolean(right, scope, "operand of AND")
            case n.Binary(op="OR", left=left, right=right):
                return self.boolean(left, scope, "operand of OR") or self.boolean(right, scope, "operand of OR")
            case n.Binary(op=op, left=left, right=right):
                a = self.evaluate(left, scope)
                b = self.evaluate(right, scope)
                if op == "==":
                    return self.wrap(lambda: v.equals(a, b), node.pos)
                if op == "!=":
                    return not self.wrap(lambda: v.equals(a, b), node.pos)
                if op in v.COMPARISON:
                    return self.wrap(lambda: v.compare(op, a, b), node.pos)
                return self.wrap(lambda: v.BINARY[op](a, b), node.pos)
            case n.Unary(op="NOT", operand=operand):
                return not self.boolean(operand, scope, "operand of NOT")
            case n.Unary(op="-", operand=operand):
                a = self.evaluate(operand, scope)
                return self.wrap(lambda: v.neg(a), node.pos)
            case n.ListLit(items=items):
                return [self.evaluate(item, scope) for item in items]
            case n.MapLit(entries=entries):
                result = v.FMap()
                for key_expr, value_expr in entries:
                    key = self.evaluate(key_expr, scope)
                    value = self.evaluate(value_expr, scope)
                    self.wrap(lambda: result.__setitem__(key, value), n.start(key_expr))
                return result
            case n.Index(target=target, index=index):
                return self.get_index(self.evaluate(target, scope), self.evaluate(index, scope), node.pos)
            case n.Call(callee=callee, args=arg_exprs):
                fn = self.evaluate(callee, scope)
                args = [self.evaluate(arg, scope) for arg in arg_exprs]
                return self.call(fn, args, node.pos)
            case n.Member():
                target = self.evaluate(node.target, scope)
                raise self.error(FalaszTypeError, f"{v.type_name(target)} has no members", node.pos)
        raise AssertionError(f"unexpected expression {node!r}")

    def wrap(self, fn, pos: Pos) -> Any:
        try:
            return fn()
        except FalaszError as err:
            raise self.located(err, pos)

    def call(self, fn: Any, args: list[Any], pos: Pos) -> Any:
        """Call `fn` with already evaluated arguments; `pos` is the call's '('."""
        t = type(fn)
        if t is v.Function:
            return self.call_function(fn, args, pos)
        if t is not v.Builtin:
            raise self.error(FalaszTypeError, f"{v.type_name(fn)} is not callable", pos)
        if not fn.min_args <= len(args) <= fn.max_args:
            expected = (str(fn.min_args) if fn.min_args == fn.max_args
                        else f"{fn.min_args} to {fn.max_args}")
            raise self.error(FalaszArityError,
                             f"{fn.name} expects {expected} argument(s), got {len(args)}", pos)
        return self.wrap(lambda: fn.fn(self, args), pos)

    def call_function(self, fn: v.Function, args: list[Any], pos: Pos) -> Any:
        if len(args) != len(fn.params):
            raise self.error(FalaszArityError,
                             f"{fn.name} expects {len(fn.params)} argument(s), got {len(args)}", pos)
        if len(self.frames) > self.max_depth:  # frames[0] is <main>
            raise self.error(FalaszRecursionLimitError,
                             f"maximum call depth of {self.max_depth} exceeded", pos)
        scope = Scope(fn.closure)
        scope.vars.update(zip(fn.params, args))
        caller = self.frames[-1]
        self.frames.append(Frame(fn.name, fn.path))
        try:
            self.block(fn.body, scope)
        except _Return as ret:
            return ret.value
        except RecursionError:
            # The Python stack ran out before max_depth (very deep expressions in
            # every frame); report it as a Falasz error, never a Python crash.
            err = self.error(FalaszRecursionLimitError, "call stack exhausted", pos)
            err.trace = [TraceEntry(caller.path, pos, caller.name)]
            raise err from None
        except FalaszError as err:
            if not err.trace:  # innermost frame: where the error happened
                err.trace.append(TraceEntry(err.path, err.pos, fn.name))
            err.trace.insert(0, TraceEntry(caller.path, pos, caller.name))
            raise
        finally:
            self.frames.pop()
        return None

    # ----------------------------------------------------------- indexing

    def check_list_index(self, container: list | str, index: Any, pos: Pos) -> None:
        if type(index) is not int:
            raise self.error(FalaszTypeError,
                             f"{v.type_name(container)} index must be INTEGER, not {v.type_name(index)}", pos)
        if not 0 <= index < len(container):
            raise self.error(FalaszIndexError,
                             f"index {index} out of range for {v.type_name(container)} of length {len(container)}", pos)

    def get_index(self, container: Any, index: Any, pos: Pos) -> Any:
        t = type(container)
        if t is list or t is str:
            self.check_list_index(container, index, pos)
            return container[index]
        if t is v.FMap:
            if not self.wrap(lambda: index in container, pos):
                raise self.error(FalaszKeyError, f"key {v.show(index)} not found in MAP", pos)
            return container.get(index)
        raise self.error(FalaszTypeError, f"{v.type_name(container)} cannot be indexed", pos)

    def set_index(self, container: Any, index: Any, value: Any, pos: Pos) -> None:
        t = type(container)
        if t is list:
            self.check_list_index(container, index, pos)
            container[index] = value
        elif t is v.FMap:
            self.wrap(lambda: container.__setitem__(index, value), pos)
        elif t is str:
            raise self.error(FalaszTypeError, "STRING is immutable; cannot assign to an index", pos)
        else:
            raise self.error(FalaszTypeError, f"{v.type_name(container)} does not support index assignment", pos)
