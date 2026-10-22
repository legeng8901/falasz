"""Token definitions (docs/spec.md, section 2)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import Pos


class T(Enum):
    # Literals and names
    INTEGER = "integer literal"
    FLOAT = "float literal"
    STRING = "string literal"
    IDENT = "identifier"
    # Keywords
    LET = "LET"
    SAY = "SAY"
    IF = "IF"
    ELSE = "ELSE"
    WHILE = "WHILE"
    FOR = "FOR"
    IN = "IN"
    FUNC = "FUNC"
    RETURN = "RETURN"
    END = "END"
    BREAK = "BREAK"
    CONTINUE = "CONTINUE"
    IMPORT = "IMPORT"
    LOCAL = "LOCAL"
    AS = "AS"
    EXPORT = "EXPORT"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NULL = "NULL"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    # Operators and punctuation
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    EQ = "=="
    NE = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="
    ASSIGN = "="
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"
    COMMA = ","
    DOT = "."
    COLON = ":"
    # Structure
    NEWLINE = "end of line"
    EOF = "end of file"


KEYWORDS = {
    t.value: t
    for t in T
    if t.value.isalpha() and t.value.isupper()
}

# Longest operators first so that "<=" wins over "<".
OPERATORS = sorted(
    (t for t in T if not t.value[0].isalnum() and " " not in t.value),
    key=lambda t: -len(t.value),
)


@dataclass(frozen=True, slots=True)
class Token:
    type: T
    text: str
    pos: Pos

    def describe(self) -> str:
        if self.type in (T.NEWLINE, T.EOF):
            return self.type.value
        if self.type in (T.INTEGER, T.FLOAT, T.STRING, T.IDENT):
            return f"{self.type.value} {self.text}"
        return f"'{self.text}'"
