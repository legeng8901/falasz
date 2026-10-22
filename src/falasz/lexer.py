"""Source decoding and tokenization (docs/spec.md, sections 1-2)."""

from __future__ import annotations

from .errors import FalaszLimitError, FalaszSyntaxError, Pos
from .tokens import KEYWORDS, OPERATORS, T, Token

MAX_SOURCE_BYTES = 1024 * 1024

_ESCAPES = {'"': '"', "\\": "\\", "n": "\n", "t": "\t"}
_OPENERS = {T.LPAREN, T.LBRACKET, T.LBRACE}
_CLOSERS = {T.RPAREN, T.RBRACKET, T.RBRACE}


def decode_source(data: bytes, path: str) -> str:
    """Decode a source file: size limit, optional BOM, strict UTF-8."""
    if len(data) > MAX_SOURCE_BYTES:
        raise FalaszLimitError(f"source file is larger than the limit of {MAX_SOURCE_BYTES} bytes", path)
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        head = data[: exc.start]
        line = head.count(b"\n") + 1
        column = len(head[head.rfind(b"\n") + 1 :].decode("utf-8", "replace")) + 1
        raise FalaszSyntaxError("invalid UTF-8 in source file", path, Pos(line, column)) from None


def _is_ident_start(ch: str) -> bool:
    return ch == "_" or ("a" <= ch <= "z") or ("A" <= ch <= "Z")


def _is_ident_char(ch: str) -> bool:
    return _is_ident_start(ch) or ("0" <= ch <= "9")


def _is_digit(ch: str) -> bool:
    return "0" <= ch <= "9"


class Lexer:
    def __init__(self, source: str, path: str):
        # All line endings become "\n" so positions match on Linux and Windows.
        self.src = source.replace("\r\n", "\n").replace("\r", "\n")
        self.path = path
        self.i = 0
        self.line = 1
        self.col = 1
        self.depth = 0  # bracket nesting; newlines inside brackets are ignored
        self.tokens: list[Token] = []

    def error(self, message: str, pos: Pos) -> FalaszSyntaxError:
        return FalaszSyntaxError(message, self.path, pos)

    def peek(self, offset: int = 0) -> str:
        j = self.i + offset
        return self.src[j] if j < len(self.src) else ""

    def advance(self) -> str:
        ch = self.src[self.i]
        self.i += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def emit(self, type_: T, text: str, pos: Pos) -> None:
        if type_ is T.NEWLINE and (not self.tokens or self.tokens[-1].type is T.NEWLINE):
            return  # collapse blank lines and skip leading newlines
        self.tokens.append(Token(type_, text, pos))

    def tokenize(self) -> list[Token]:
        while self.i < len(self.src):
            ch = self.peek()
            pos = Pos(self.line, self.col)
            if ch == "\n":
                self.advance()
                if self.depth == 0:
                    self.emit(T.NEWLINE, "\n", pos)
            elif ch in " \t\f\v":
                self.advance()
            elif ch == "#":
                while self.i < len(self.src) and self.peek() != "\n":
                    self.advance()
            elif ch == '"':
                self.string(pos)
            elif _is_digit(ch):
                self.number(pos)
            elif _is_ident_start(ch):
                self.word(pos)
            else:
                self.operator(pos)
        end = Pos(self.line, self.col)
        self.emit(T.NEWLINE, "", end)
        self.tokens.append(Token(T.EOF, "", end))
        return self.tokens

    def string(self, start: Pos) -> None:
        self.advance()  # opening quote
        chars: list[str] = []
        while True:
            ch = self.peek()
            if ch == "" or ch == "\n":
                raise self.error("unterminated string literal", start)
            if ch == '"':
                self.advance()
                break
            if ch == "\\":
                esc_pos = Pos(self.line, self.col)
                self.advance()
                esc = self.peek()
                if esc not in _ESCAPES:
                    shown = esc if esc != "\n" else ""
                    raise self.error(f"invalid escape sequence '\\{shown}'", esc_pos)
                self.advance()
                chars.append(_ESCAPES[esc])
            else:
                chars.append(self.advance())
        self.tokens.append(Token(T.STRING, "".join(chars), start))

    def number(self, start: Pos) -> None:
        begin = self.i
        while _is_digit(self.peek()):
            self.advance()
        type_ = T.INTEGER
        if self.peek() == ".":
            if not _is_digit(self.peek(1)):
                raise self.error("invalid float literal: digits required after '.'", start)
            type_ = T.FLOAT
            self.advance()
            while _is_digit(self.peek()):
                self.advance()
        text = self.src[begin : self.i]
        if _is_ident_char(self.peek()) or self.peek() == ".":
            raise self.error(f"invalid number literal '{text}{self.peek()}'", start)
        integer_part = text.split(".")[0]
        if len(integer_part) > 1 and integer_part[0] == "0":
            raise self.error(f"leading zeros are not allowed in '{text}'", start)
        self.tokens.append(Token(type_, text, start))

    def word(self, start: Pos) -> None:
        begin = self.i
        while _is_ident_char(self.peek()):
            self.advance()
        text = self.src[begin : self.i]
        if self.peek().isalnum():  # non-ASCII letter glued to an identifier
            raise self.error(
                f"identifiers may contain only ASCII letters, digits and '_' (found '{self.peek()}')",
                Pos(self.line, self.col),
            )
        self.tokens.append(Token(KEYWORDS.get(text, T.IDENT), text, start))

    def operator(self, start: Pos) -> None:
        for op in OPERATORS:
            if self.src.startswith(op.value, self.i):
                for _ in op.value:
                    self.advance()
                if op in _OPENERS:
                    self.depth += 1
                elif op in _CLOSERS and self.depth > 0:
                    self.depth -= 1
                self.tokens.append(Token(op, op.value, start))
                return
        raise self.error(f"unexpected character '{self.peek()}'", start)


def tokenize(source: str, path: str = "<input>") -> list[Token]:
    return Lexer(source, path).tokenize()
