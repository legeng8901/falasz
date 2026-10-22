"""Static module loading (docs/spec.md, section 9.1).

Starting from the main script, every reachable local module is read, parsed and
validated *before* anything executes. The loader:
  - resolves each IMPORT (standard library first unless LOCAL; local files are
    `<name>.falasz` in the importing file's directory) and stores the result in
    `Import.resolved`;
  - detects import cycles and reports them at the IMPORT that closes the cycle;
  - gives the validator the export list of every imported module so that
    `module.member` is checked statically;
  - never executes code and never imports Python code.

Modules are identified by their canonical path (symlinks resolved). Module
names are ASCII identifiers, so an IMPORT can never contain a path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import nodes as n
from .errors import FalaszError, FalaszImportError, Pos
from .lexer import decode_source
from .parser import parse
from .stdlib import STDLIB_EXPORTS
from .validator import validate

SOURCE_SUFFIX = ".falasz"
STD_PREFIX = "std:"

# Device names that Windows reserves in every directory; refusing them on every
# platform keeps programs portable (a module named CON cannot exist on Windows).
WINDOWS_RESERVED = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


@dataclass
class SourceFile:
    key: str  # canonical path
    display: str  # path shown in diagnostics
    program: n.Program | None = None
    exports: frozenset[str] | None = None  # None: unknown (file has a syntax error)
    errors: list[FalaszError] = field(default_factory=list)


@dataclass
class LoaderWarning:
    path: str
    pos: Pos
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.pos.line}:{self.pos.column}: Warning: {self.message}"


def canonical(path: str) -> str:
    return os.path.realpath(os.path.abspath(path))


def _exists_with_exact_name(path: str) -> bool:
    """True if `path` is a regular file whose name matches exactly, also on
    case-insensitive file systems (so programs behave the same everywhere)."""
    if not os.path.isfile(path):
        return False
    try:
        return os.path.basename(path) in os.listdir(os.path.dirname(path))
    except OSError:
        return False


class ModuleLoader:
    def __init__(self, main_path: str, main_source: str | None = None):
        self.main_path = main_path
        self.main_key = canonical(main_path)
        self.base_dir = os.path.dirname(self.main_key)
        self.main_source = main_source
        self.files: dict[str, SourceFile] = {}  # discovery order
        self.warnings: list[LoaderWarning] = []

    # ----------------------------------------------------------- public API

    def load(self) -> list[FalaszError]:
        """Load the whole program; returns all static errors (main file first)."""
        main = SourceFile(self.main_key, self.main_path)
        self.files[main.key] = main
        source = self.main_source
        if source is None:
            source = self.read_source(main)
        if source is not None:
            self.load_file(main, source, [main.key])
        return [err for f in self.files.values() for err in f.errors]

    @property
    def main(self) -> SourceFile:
        return self.files[self.main_key]

    def programs(self) -> dict[str, tuple[n.Program, str]]:
        return {k: (f.program, f.display) for k, f in self.files.items() if f.program is not None}

    # ------------------------------------------------------------- internals

    def display_path(self, key: str) -> str:
        rel = os.path.relpath(key, self.base_dir)
        return rel.replace(os.sep, "/")

    def read_source(self, file: SourceFile) -> str | None:
        try:
            with open(file.key, "rb") as f:
                data = f.read()
            return decode_source(data, file.display)
        except FalaszError as err:
            file.errors.append(err)
        except OSError as exc:
            file.errors.append(FalaszImportError(f"cannot read source file: {exc.strerror}", file.display))
        return None

    def load_file(self, file: SourceFile, source: str, stack: list[str]) -> None:
        try:
            program = parse(source, file.display)
        except FalaszError as err:
            file.errors.append(err)
            return
        file.program = program
        file.exports = frozenset(
            name for stmt in program.body if isinstance(stmt, n.Export) for name, _ in stmt.names
        )
        imported: dict[str, frozenset[str] | None] = {}
        for stmt in program.body:
            if isinstance(stmt, n.Import):
                imported[stmt.binding] = self.resolve(stmt, file, stack)
        file.errors.extend(validate(program, imported))
        file.errors.sort(key=lambda e: (e.pos or Pos(0, 0)))

    def resolve(self, stmt: n.Import, file: SourceFile, stack: list[str]) -> frozenset[str] | None:
        """Resolve one IMPORT; returns the module's export names (None = unknown)."""
        def fail(message: str) -> None:
            file.errors.append(FalaszImportError(message, file.display, stmt.pos))

        directory = os.path.dirname(file.key)
        candidate = os.path.join(directory, stmt.module + SOURCE_SUFFIX)

        if not stmt.local and stmt.module in STDLIB_EXPORTS:
            if _exists_with_exact_name(candidate):
                self.warnings.append(LoaderWarning(
                    file.display, stmt.pos,
                    f"'IMPORT {stmt.module}' uses the standard library module; the local file "
                    f"{self.display_path(canonical(candidate))} is ignored "
                    f"(use 'IMPORT LOCAL {stmt.module} AS ...' to import it)",
                ))
            stmt.resolved = STD_PREFIX + stmt.module
            return STDLIB_EXPORTS[stmt.module]

        if stmt.module.upper() in WINDOWS_RESERVED:
            fail(f"'{stmt.module}' is a reserved device name on Windows and cannot be a module name")
            return None
        if not _exists_with_exact_name(candidate):
            looked = self.display_path(canonical(candidate))
            where = looked if stmt.local else f"the standard library and {looked}"
            fail(f"cannot find module '{stmt.module}' (looked in {where})")
            return None

        key = canonical(candidate)
        stmt.resolved = key
        if key in stack:
            chain = [self.files[k].display for k in stack[stack.index(key):]] + [self.files[key].display]
            fail("import cycle: " + " -> ".join(chain))
            return None
        if key not in self.files:
            module = SourceFile(key, self.display_path(key))
            self.files[key] = module
            source = self.read_source(module)
            if source is not None:
                self.load_file(module, source, stack + [key])
        return self.files[key].exports
