"""Diagnostics shared by every interpreter phase (docs/spec.md, section 11)."""

from __future__ import annotations

from typing import NamedTuple


class Pos(NamedTuple):
    """1-based line and column (in code points) inside one source file."""

    line: int
    column: int


class FalaszError(Exception):
    """Base class of all errors reported to Falasz users.

    `category` is the name shown in diagnostics (e.g. "SyntaxError"); the Python
    class names carry a `Falasz` prefix so they never shadow Python builtins.
    """

    category = "Error"

    def __init__(self, message: str, path: str | None = None, pos: Pos | None = None):
        super().__init__(message)
        self.message = message
        self.path = path
        self.pos = pos
        # Call stack for errors raised inside user functions, outermost first:
        # (path, position currently executing in that frame, frame name).
        self.trace: list[TraceEntry] = []

    def format(self) -> str:
        if self.path is None:
            return f"{self.category}: {self.message}"
        if self.pos is None:
            return f"{self.path}: {self.category}: {self.message}"
        return f"{self.path}:{self.pos.line}:{self.pos.column}: {self.category}: {self.message}"

    def __str__(self) -> str:
        return self.format()

    def format_with_trace(self) -> str:
        """Diagnostic preceded by the call stack (spec 11.1), if there is one."""
        if not self.trace:
            return self.format()
        lines = ["Traceback:"]
        for text, count in _collapse([f"  {p}:{pos.line}:{pos.column} in {name}" for p, pos, name in self.trace]):
            lines.append(text)
            if count > 1:
                lines.append(f"  [previous line repeated {count - 1} more times]")
        lines.append(self.format())
        return "\n".join(lines)


class TraceEntry(NamedTuple):
    path: str
    pos: Pos
    name: str


def _collapse(lines: list[str]) -> list[tuple[str, int]]:
    """Run-length encode consecutive identical lines (deep recursion)."""
    runs: list[tuple[str, int]] = []
    for line in lines:
        if runs and runs[-1][0] == line:
            runs[-1] = (line, runs[-1][1] + 1)
        else:
            runs.append((line, 1))
    return runs


def _category(name: str) -> type[FalaszError]:
    return type(f"Falasz{name}", (FalaszError,), {"category": name, "__module__": __name__})


FalaszSyntaxError = _category("SyntaxError")
FalaszNameError = _category("NameError")
FalaszTypeError = _category("TypeError")
FalaszValueError = _category("ValueError")
FalaszArityError = _category("ArityError")
FalaszZeroDivisionError = _category("ZeroDivisionError")
FalaszArithmeticError = _category("ArithmeticError")
FalaszIndexError = _category("IndexError")
FalaszKeyError = _category("KeyError")
FalaszImportError = _category("ImportError")
FalaszFileError = _category("FileError")
FalaszSensorError = _category("SensorError")
FalaszRecursionLimitError = _category("RecursionLimitError")
FalaszLimitError = _category("LimitError")
# Temporary category for language features of later implementation stages.
FalaszNotImplementedError = _category("NotImplementedError")
