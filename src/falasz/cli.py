"""Command-line interface (docs/spec.md, sections 11.3-11.4).

    falasz run [--sensors-mock FILE] [--max-steps N] FILE
    falasz check FILE
    falasz --version

Exit codes: 0 success, 1 runtime error, 2 command-line usage error (including an
unreadable input file or invalid sensor mock data), 3 syntax/validation/import
error, 70 internal interpreter error, 130 interrupted (Ctrl+C).

Program output (SAY, INPUT prompts) goes to stdout as UTF-8 with "\\n" line endings
on every platform; diagnostics and warnings go to stderr.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from typing import TextIO

from . import __version__
from .errors import FalaszError
from .runtime import StaticErrors, check_file, run_file
from .sensors import MockSensorProvider, SensorConfigError

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_USAGE = 2
EXIT_STATIC = 3
EXIT_INTERNAL = 70
EXIT_INTERRUPTED = 130


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # argparse would exit; keep control of codes
        self.print_usage(sys.stderr)
        raise _UsageError(message)


class _UsageError(Exception):
    pass


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid positive integer: {text!r}") from None
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="falasz",
        description="Falasz programming language - reference interpreter (v0.1 alpha).",
    )
    parser.add_argument("--version", action="version", version=f"falasz {__version__}")
    parser.add_argument("--debug", action="store_true",
                        help="show Python tracebacks for internal interpreter errors")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.required = True

    run = commands.add_parser("run", help="check and run a program")
    run.add_argument("file", metavar="FILE", help="the .falasz program to run")
    run.add_argument("--sensors-mock", metavar="FILE",
                     help="JSON file with mock sensor data (see docs/sensors.md)")
    run.add_argument("--max-steps", metavar="N", type=_positive_int,
                     help="stop with LimitError after N executed steps")

    check = commands.add_parser("check", help="check syntax, names and imports without running anything")
    check.add_argument("file", metavar="FILE", help="the .falasz program to check")
    return parser


def _use_utf8_lf(stream: TextIO) -> None:
    """UTF-8 and '\\n' (no CRLF translation) on the real console streams."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None and stream in (sys.__stdout__, sys.__stderr__):
        reconfigure(encoding="utf-8", errors="backslashreplace", newline="\n")


def _check_input_file(path: str) -> None:
    if not os.path.exists(path):
        raise _UsageError(f"cannot open {path!r}: no such file")
    if os.path.isdir(path):
        raise _UsageError(f"cannot open {path!r}: is a directory")
    if not os.access(path, os.R_OK):
        raise _UsageError(f"cannot open {path!r}: permission denied")


def _print_warnings(result, err: TextIO) -> None:
    for warning in result.warnings:
        print(warning.format(), file=err)


def _cmd_check(args, out: TextIO, err: TextIO) -> int:
    result = check_file(args.file)
    _print_warnings(result, err)
    if result.errors:
        for error in result.errors:
            print(error.format(), file=err)
        count = len(result.errors)
        print(f"{count} error{'s' if count != 1 else ''} found", file=err)
        return EXIT_STATIC
    print("OK", file=out)
    return EXIT_OK


def _cmd_run(args, out: TextIO, err: TextIO, stdin) -> int:
    sensors = None
    if args.sensors_mock is not None:
        try:
            sensors = MockSensorProvider.from_json_file(args.sensors_mock)
        except SensorConfigError as exc:
            raise _UsageError(f"invalid --sensors-mock data: {exc}") from None
    try:
        result = run_file(args.file, out=out, inp=stdin, max_steps=args.max_steps, sensors=sensors)
    except StaticErrors as exc:
        out.flush()
        for error in exc.errors:
            print(error.format(), file=err)
        return EXIT_STATIC
    except FalaszError as exc:
        out.flush()
        print(exc.format_with_trace(), file=err)
        return EXIT_RUNTIME
    out.flush()
    _print_warnings(result, err)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    out, err = sys.stdout, sys.stderr
    _use_utf8_lf(out)
    _use_utf8_lf(err)
    stdin = getattr(sys.stdin, "buffer", None)
    args = None
    try:
        args = build_parser().parse_args(argv)
        _check_input_file(args.file)
        if args.command == "check":
            return _cmd_check(args, out, err)
        return _cmd_run(args, out, err, stdin)
    except _UsageError as exc:
        print(f"falasz: error: {exc}", file=err)
        return EXIT_USAGE
    except SystemExit as exc:  # --help / --version
        return exc.code if isinstance(exc.code, int) else EXIT_OK
    except KeyboardInterrupt:
        print("falasz: interrupted", file=err)
        return EXIT_INTERRUPTED
    except BrokenPipeError:
        # stdout was closed early (e.g. `falasz run prog.falasz | head`): stop quietly.
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except (OSError, ValueError):
            pass
        return EXIT_RUNTIME
    except Exception as exc:  # noqa: BLE001 - last line of defence
        if args is not None and args.debug:
            traceback.print_exc(file=err)
        print(f"InternalError: {type(exc).__name__}: {exc}", file=err)
        print("This is a bug in the Falasz interpreter; please report it "
              "(run with --debug for details).", file=err)
        return EXIT_INTERNAL


def entry_point() -> None:
    sys.exit(main())
