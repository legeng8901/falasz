"""Recursive-descent parser for the grammar in docs/spec.md, section 3.

Besides building the AST, the parser enforces the syntactic part of static
validation (spec 7.1): RETURN/BREAK/CONTINUE/IMPORT/EXPORT placement, duplicate
parameters, chained comparisons, expression statements and assignment targets.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager

from . import nodes as n
from .errors import FalaszNameError, FalaszSyntaxError, Pos
from .lexer import tokenize
from .tokens import T, Token

MAX_NESTING = 200

_COMPARISON = {T.EQ, T.NE, T.LT, T.GT, T.LE, T.GE}
_ADDITIVE = {T.PLUS, T.MINUS}
_MULTIPLICATIVE = {T.STAR, T.SLASH, T.PERCENT}
_LINE_END = {T.NEWLINE, T.EOF}


class Parser:
    def __init__(self, tokens: list[Token], path: str):
        self.tokens = tokens
        self.path = path
        self.i = 0
        self.nesting = 0
        self.function_depth = 0
        self.loop_depth = 0  # loops inside the innermost function (or the module)
        self.block_depth = 0  # any enclosing block; IMPORT/EXPORT need 0

    # ------------------------------------------------------------- helpers

    @property
    def tok(self) -> Token:
        return self.tokens[self.i]

    def at(self, *types: T) -> bool:
        return self.tok.type in types

    def advance(self) -> Token:
        token = self.tokens[self.i]
        if token.type is not T.EOF:
            self.i += 1
        return token

    def error(self, message: str, pos: Pos | None = None) -> FalaszSyntaxError:
        return FalaszSyntaxError(message, self.path, pos or self.tok.pos)

    def unexpected(self, expected: str) -> FalaszSyntaxError:
        return self.error(f"expected {expected}, found {self.tok.describe()}")

    def expect(self, type_: T, expected: str | None = None) -> Token:
        if not self.at(type_):
            if expected is None:
                expected = type_.value if type_ in _LINE_END else f"'{type_.value}'"
            raise self.unexpected(expected)
        return self.advance()

    def expect_line_end(self) -> None:
        if not self.at(*_LINE_END):
            raise self.unexpected("end of line")
        if self.at(T.NEWLINE):
            self.advance()

    @contextmanager
    def nested(self):
        self.nesting += 1
        if self.nesting > MAX_NESTING:
            raise self.error(f"nesting too deep (limit {MAX_NESTING})")
        try:
            yield
        finally:
            self.nesting -= 1

    # ---------------------------------------------------------- statements

    def program(self) -> n.Program:
        if self.at(T.NEWLINE):
            self.advance()
        body = []
        while not self.at(T.EOF):
            body.append(self.statement())
            self.expect_line_end()
        return n.Program(body, self.path)

    def block(self, *terminators: T) -> list[n.Stmt]:
        """Statements up to (not including) one of `terminators`."""
        with self.nested():
            self.block_depth += 1
            try:
                if self.at(T.NEWLINE):
                    self.advance()
                body = []
                while not self.at(*terminators):
                    if self.at(T.EOF):
                        names = " or ".join(t.value for t in terminators)
                        raise self.error(f"expected {names} before end of file")
                    body.append(self.statement())
                    self.expect_line_end()
                return body
            finally:
                self.block_depth -= 1

    def statement(self) -> n.Stmt:
        match self.tok.type:
            case T.IMPORT:
                return self.import_stmt()
            case T.EXPORT:
                return self.export_stmt()
            case T.LET:
                pos = self.advance().pos
                name = self.expect(T.IDENT, "variable name")
                self.expect(T.ASSIGN)
                return n.Let(name.text, self.expression(), pos, name.pos)
            case T.FUNC:
                return self.func_stmt()
            case T.IF:
                return self.if_stmt(consume_end=True)
            case T.WHILE:
                pos = self.advance().pos
                cond = self.expression()
                self.expect_line_end()
                body = self.loop_body()
                self.expect(T.END)
                return n.While(cond, body, pos)
            case T.FOR:
                pos = self.advance().pos
                var = self.expect(T.IDENT, "loop variable name")
                self.expect(T.IN)
                iterable = self.expression()
                self.expect_line_end()
                body = self.loop_body()
                self.expect(T.END)
                return n.For(var.text, iterable, body, pos, var.pos)
            case T.SAY:
                pos = self.advance().pos
                return n.Say(self.expression(), pos)
            case T.RETURN:
                pos = self.tok.pos
                if self.function_depth == 0:
                    raise self.error("RETURN outside of a function")
                self.advance()
                value = None if self.at(*_LINE_END) else self.expression()
                return n.Return(value, pos)
            case T.END:
                raise self.error("'END' without a matching block")
            case T.ELSE:
                raise self.error("'ELSE' without a matching IF")
            case T.BREAK | T.CONTINUE:
                if self.loop_depth == 0:
                    raise self.error(f"{self.tok.text} outside of a loop")
                token = self.advance()
                return n.Break(token.pos) if token.type is T.BREAK else n.Continue(token.pos)
            case _:
                return self.assign_or_expr()

    def loop_body(self) -> list[n.Stmt]:
        self.loop_depth += 1
        try:
            return self.block(T.END)
        finally:
            self.loop_depth -= 1

    def import_stmt(self) -> n.Import:
        if self.block_depth > 0 or self.function_depth > 0:
            raise self.error("IMPORT is only allowed at the top level of a file")
        pos = self.advance().pos
        local = self.at(T.LOCAL)
        if local:
            self.advance()
        module = self.expect(T.IDENT, "module name")
        alias = None
        binding_pos = module.pos
        if self.at(T.AS):
            self.advance()
            alias_token = self.expect(T.IDENT, "alias name")
            alias, binding_pos = alias_token.text, alias_token.pos
        return n.Import(module.text, local, alias, pos, binding_pos)

    def export_stmt(self) -> n.Export:
        if self.block_depth > 0 or self.function_depth > 0:
            raise self.error("EXPORT is only allowed at the top level of a file")
        pos = self.advance().pos
        names = []
        while True:
            name = self.expect(T.IDENT, "name to export")
            names.append((name.text, name.pos))
            if not self.at(T.COMMA):
                return n.Export(names, pos)
            self.advance()

    def func_stmt(self) -> n.Func:
        pos = self.advance().pos
        name = self.expect(T.IDENT, "function name")
        self.expect(T.LPAREN)
        params: list[tuple[str, Pos]] = []
        if not self.at(T.RPAREN):
            while True:
                param = self.expect(T.IDENT, "parameter name")
                if any(p == param.text for p, _ in params):
                    raise self.error(f"duplicate parameter '{param.text}'", param.pos)
                params.append((param.text, param.pos))
                if not self.at(T.COMMA):
                    break
                self.advance()
        self.expect(T.RPAREN)
        self.expect_line_end()
        saved_loops, self.loop_depth = self.loop_depth, 0
        self.function_depth += 1
        try:
            body = self.block(T.END)
        finally:
            self.function_depth -= 1
            self.loop_depth = saved_loops
        self.expect(T.END)
        return n.Func(name.text, params, body, pos, name.pos)

    def if_stmt(self, consume_end: bool) -> n.If:
        pos = self.advance().pos
        cond = self.expression()
        self.expect_line_end()
        then = self.block(T.END, T.ELSE)
        otherwise = None
        if self.at(T.ELSE):
            self.advance()
            if self.at(T.IF):
                with self.nested():
                    otherwise = [self.if_stmt(consume_end=False)]
            else:
                self.expect_line_end()
                otherwise = self.block(T.END)
        if consume_end:
            self.expect(T.END)
        return n.If(cond, then, otherwise, pos)

    def assign_or_expr(self) -> n.Stmt:
        expr = self.expression()
        if self.at(T.ASSIGN):
            eq = self.advance()
            if isinstance(expr, n.Member):
                raise FalaszNameError("module members are read-only", self.path, expr.pos)
            if not isinstance(expr, (n.Name, n.Index)):
                raise self.error("invalid assignment target", n.start(expr))
            return n.Assign(expr, self.expression(), eq.pos)
        if not isinstance(expr, n.Call):
            raise self.error("expression has no effect; only function calls can be used as statements",
                             n.start(expr))
        return n.ExprStmt(expr, n.start(expr))

    # --------------------------------------------------------- expressions

    def expression(self) -> n.Expr:
        with self.nested():
            return self.or_expr()

    def or_expr(self) -> n.Expr:
        left = self.and_expr()
        while self.at(T.OR):
            pos = self.advance().pos
            left = n.Binary("OR", left, self.and_expr(), pos)
        return left

    def and_expr(self) -> n.Expr:
        left = self.not_expr()
        while self.at(T.AND):
            pos = self.advance().pos
            left = n.Binary("AND", left, self.not_expr(), pos)
        return left

    def not_expr(self) -> n.Expr:
        if self.at(T.NOT):
            pos = self.advance().pos
            with self.nested():
                return n.Unary("NOT", self.not_expr(), pos)
        return self.comparison()

    def comparison(self) -> n.Expr:
        left = self.additive()
        if self.at(*_COMPARISON):
            op = self.advance()
            left = n.Binary(op.text, left, self.additive(), op.pos)
            if self.at(*_COMPARISON):
                raise self.error("comparison operators cannot be chained; use AND")
        return left

    def additive(self) -> n.Expr:
        left = self.multiplicative()
        while self.at(*_ADDITIVE):
            op = self.advance()
            left = n.Binary(op.text, left, self.multiplicative(), op.pos)
        return left

    def multiplicative(self) -> n.Expr:
        left = self.unary()
        while self.at(*_MULTIPLICATIVE):
            op = self.advance()
            left = n.Binary(op.text, left, self.unary(), op.pos)
        return left

    def unary(self) -> n.Expr:
        if self.at(T.MINUS):
            pos = self.advance().pos
            with self.nested():
                return n.Unary("-", self.unary(), pos)
        return self.postfix()

    def postfix(self) -> n.Expr:
        expr = self.primary()
        while True:
            if self.at(T.LPAREN):
                pos = self.advance().pos
                args = self.comma_list(T.RPAREN, self.expression)
                expr = n.Call(expr, args, pos)
            elif self.at(T.LBRACKET):
                pos = self.advance().pos
                index = self.expression()
                self.expect(T.RBRACKET)
                expr = n.Index(expr, index, pos)
            elif self.at(T.DOT):
                pos = self.advance().pos
                name = self.expect(T.IDENT, "member name")
                expr = n.Member(expr, name.text, pos, name.pos)
            else:
                return expr

    def comma_list(self, closer: T, item):
        """Items separated by commas, optional trailing comma, consumes `closer`."""
        items = []
        while not self.at(closer):
            items.append(item())
            if not self.at(T.COMMA):
                break
            self.advance()
        self.expect(closer)
        return items

    def primary(self) -> n.Expr:
        token = self.tok
        match token.type:
            case T.INTEGER:
                self.advance()
                return n.IntLit(int(token.text), token.pos)
            case T.FLOAT:
                self.advance()
                value = float(token.text)
                if value == float("inf"):
                    raise self.error("float literal out of range", token.pos)
                return n.FloatLit(value, token.pos)
            case T.STRING:
                self.advance()
                return n.StrLit(token.text, token.pos)
            case T.TRUE | T.FALSE:
                self.advance()
                return n.BoolLit(token.type is T.TRUE, token.pos)
            case T.NULL:
                self.advance()
                return n.NullLit(token.pos)
            case T.IDENT:
                self.advance()
                return n.Name(token.text, token.pos)
            case T.LPAREN:
                self.advance()
                expr = self.expression()
                self.expect(T.RPAREN)
                return expr
            case T.LBRACKET:
                self.advance()
                return n.ListLit(self.comma_list(T.RBRACKET, self.expression), token.pos)
            case T.LBRACE:
                self.advance()
                return n.MapLit(self.comma_list(T.RBRACE, self.map_entry), token.pos)
        raise self.unexpected("an expression")

    def map_entry(self) -> tuple[n.Expr, n.Expr]:
        key = self.expression()
        self.expect(T.COLON)
        return key, self.expression()


def parse(source: str, path: str = "<input>") -> n.Program:
    """Tokenize and parse one source file; raises FalaszSyntaxError (or FalaszNameError)."""
    tokens = tokenize(source, path)
    # Each nesting level costs ~10 Python frames; make sure MAX_NESTING, not
    # Python's recursion limit, is what stops deeply nested input.
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, MAX_NESTING * 20 + 1000))
    try:
        return Parser(tokens, path).program()
    finally:
        sys.setrecursionlimit(old_limit)
