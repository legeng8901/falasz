"""Entry points tying the phases together: parse -> validate -> execute."""

from __future__ import annotations

from typing import BinaryIO, TextIO

from . import nodes as n
from .errors import FalaszError
from .interpreter import Interpreter
from .parser import parse
from .validator import validate


class StaticErrors(Exception):
    """Syntax/validation errors found before execution (CLI exit code 3)."""

    def __init__(self, errors: list[FalaszError]):
        super().__init__("\n".join(e.format() for e in errors))
        self.errors = errors


def check_source(source: str, path: str = "<input>") -> tuple[n.Program | None, list[FalaszError]]:
    """Parse and validate without executing anything."""
    try:
        program = parse(source, path)
    except FalaszError as err:
        return None, [err]
    return program, validate(program)


def run_source(
    source: str,
    path: str = "<input>",
    *,
    out: TextIO | None = None,
    inp: BinaryIO | None = None,
    max_steps: int | None = None,
) -> None:
    program, errors = check_source(source, path)
    if errors:
        raise StaticErrors(errors)
    assert program is not None
    Interpreter(path, out=out, inp=inp, max_steps=max_steps).run(program)
