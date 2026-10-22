"""Standard library modules `files` and `sensors` (docs/spec.md, sections 9.3-9.4).

`sensors` delegates to the interpreter's sensor provider (falasz.sensors) and
validates whatever the provider returns.

`files` is deliberately *not* a sandbox: it has the permissions of the process.
What it guarantees is deterministic path resolution (relative paths always use
the main script's directory, never the current working directory), UTF-8 without
newline translation, a read size limit, and FileError for every I/O failure.
"""

from __future__ import annotations

import os
import os.path
from typing import Any

from .errors import FalaszError, FalaszFileError, FalaszSensorError, FalaszTypeError
from .sensors import is_reading
from .values import Builtin, quote, type_name

MAX_READ_BYTES = 16 * 1024 * 1024

def resolve_path(path: str, base_dir: str, pathmod: Any = os.path) -> str:
    """Absolute path for a `files` argument (spec 9.3).

    `pathmod` is `os.path` in production; tests pass `ntpath`/`posixpath` to
    check the rules of the other platform.
    """
    if path == "":
        raise FalaszFileError("path must not be empty")
    if "\0" in path:
        raise FalaszFileError(f"path {quote(path)} contains a NUL character")
    drive, rest = pathmod.splitdrive(path)
    if drive and not rest.startswith(("/", "\\")) and pathmod.sep == "\\":
        # "C:data.txt" is relative to drive C's *current directory* on Windows,
        # which would make the result depend on the working directory.
        raise FalaszFileError(f"drive-relative path {quote(path)} is not supported; use an absolute path")
    if pathmod.sep == "\\" and not drive and path.startswith(("/", "\\")):
        # "\\data.txt" means the root of the *current* drive on Windows (and some
        # Python versions call it absolute): anchor it to the script's drive.
        return pathmod.normpath(pathmod.splitdrive(base_dir)[0] + path)
    if pathmod.isabs(path):
        return pathmod.normpath(path)
    return pathmod.normpath(pathmod.join(base_dir, path))


def _os_reason(exc: OSError) -> str:
    if isinstance(exc, FileNotFoundError):
        return "no such file or directory"
    if isinstance(exc, IsADirectoryError):
        return "is a directory"
    if isinstance(exc, NotADirectoryError):
        return "a component of the path is not a directory"
    if isinstance(exc, PermissionError):
        return "permission denied"
    return exc.strerror or type(exc).__name__


def _string_arg(fn: str, name: str, value: Any) -> str:
    if type(value) is not str:
        raise FalaszTypeError(f"{fn}: {name} must be STRING, not {type_name(value)}")
    return value


def _read_text(interp, args: list[Any]) -> str:
    path = _string_arg("files.read_text", "path", args[0])
    full = resolve_path(path, interp.base_dir)
    try:
        if os.path.isdir(full):
            raise IsADirectoryError(path)
        with open(full, "rb") as f:
            data = f.read(MAX_READ_BYTES + 1)  # never read unbounded data (e.g. /dev/zero)
    except OSError as exc:
        raise FalaszFileError(f"cannot read {quote(path)}: {_os_reason(exc)}") from None
    if len(data) > MAX_READ_BYTES:
        raise FalaszFileError(f"cannot read {quote(path)}: file is larger than {MAX_READ_BYTES} bytes")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FalaszFileError(
            f"cannot read {quote(path)}: not valid UTF-8 (byte offset {exc.start})"
        ) from None


def _write_text(interp, args: list[Any]) -> None:
    path = _string_arg("files.write_text", "path", args[0])
    content = _string_arg("files.write_text", "content", args[1])
    full = resolve_path(path, interp.base_dir)
    try:
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    except OSError as exc:
        raise FalaszFileError(f"cannot write {quote(path)}: {_os_reason(exc)}") from None
    return None


def _sensors_available(interp, args: list[Any]) -> list[str]:
    try:
        names = interp.sensors.available()
    except FalaszError:
        raise
    except Exception as exc:  # a provider talks to the outside world; never crash
        raise FalaszSensorError(f"sensor provider failed to list sensors: {exc}") from None
    if type(names) is not list or not all(type(name) is str for name in names):
        raise FalaszSensorError("sensor provider returned an invalid list of sensor names")
    return sorted(names)


def _sensors_read(interp, args: list[Any]) -> Any:
    name = _string_arg("sensors.read", "name", args[0])
    try:
        value = interp.sensors.read(name)
    except FalaszError:
        raise
    except Exception as exc:  # see _sensors_available
        raise FalaszSensorError(f"sensor {quote(name)} failed: {exc}") from None
    if not is_reading(value):
        raise FalaszSensorError(f"sensor {quote(name)} returned an invalid value ({type(value).__name__})")
    return value


STDLIB: dict[str, dict[str, Builtin]] = {
    "files": {
        "read_text": Builtin("files.read_text", 1, 1, _read_text),
        "write_text": Builtin("files.write_text", 2, 2, _write_text),
    },
    "sensors": {
        "available": Builtin("sensors.available", 0, 0, _sensors_available),
        "read": Builtin("sensors.read", 1, 1, _sensors_read),
    },
}

STDLIB_EXPORTS: dict[str, frozenset[str]] = {name: frozenset(members) for name, members in STDLIB.items()}
