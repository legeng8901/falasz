"""Entry points tying the phases together: load (parse + validate) -> execute."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, TextIO

from .errors import FalaszError
from .interpreter import Interpreter
from .modules import LoaderWarning, ModuleLoader
from .sensors import SensorProvider


class StaticErrors(Exception):
    """Syntax/validation/import errors found before execution (CLI exit code 3)."""

    def __init__(self, errors: list[FalaszError]):
        super().__init__("\n".join(e.format() for e in errors))
        self.errors = errors


@dataclass
class CheckResult:
    errors: list[FalaszError]
    warnings: list[LoaderWarning]
    loader: ModuleLoader


def check_source(source: str | None, path: str = "<input>") -> CheckResult:
    """Parse and validate a program and all local modules it imports; executes nothing.

    `source` is the main file's text (None = read `path` from disk). Imported
    modules are always read from disk, next to the importing file.
    """
    loader = ModuleLoader(path, source)
    errors = loader.load()
    return CheckResult(errors, loader.warnings, loader)


def check_file(path: str) -> CheckResult:
    return check_source(None, path)


def run_source(
    source: str | None,
    path: str = "<input>",
    *,
    out: TextIO | None = None,
    inp: BinaryIO | None = None,
    max_steps: int | None = None,
    sensors: SensorProvider | None = None,
) -> CheckResult:
    """Check the whole program, then run it; raises StaticErrors or FalaszError.

    `sensors` is the provider for the `sensors` module (default: no sensors).
    Providers are stateful, so pass a fresh one for every run.
    """
    result = check_source(source, path)
    if result.errors:
        raise StaticErrors(result.errors)
    loader = result.loader
    main = loader.main
    assert main.program is not None
    interpreter = Interpreter(
        main.display, out=out, inp=inp, max_steps=max_steps,
        modules=loader.programs(), base_dir=loader.base_dir, sensors=sensors,
    )
    interpreter.run(main.program)
    return result


def run_file(path: str, **kwargs) -> CheckResult:
    return run_source(None, path, **kwargs)
