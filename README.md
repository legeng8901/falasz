# Falasz

[![CI](https://github.com/legeng8901/falasz/actions/workflows/ci.yml/badge.svg)](https://github.com/legeng8901/falasz/actions/workflows/ci.yml)

Falasz is a small general-purpose programming language with English keywords,
explicit blocks and strict typing. This repository contains the reference
interpreter, written in Python 3.12+.

**Status: 0.1.0 alpha.** The language is fully specified for v0.1 and every
specified feature is implemented and tested. Expect breaking changes before 1.0.
See [docs/limitations.md](docs/limitations.md) for what v0.1 does not do.

```falasz
# hello.falasz
LET name = "Daniel"
LET age = 20
FUNC greet(person)
    RETURN "Hello, " + person
END
IF age >= 18
    SAY greet(name)
ELSE
    SAY "Access denied"
END
FOR number IN RANGE(1, 4)
    SAY number
END
```

```console
$ falasz run hello.falasz
Hello, Daniel
1
2
3
```

## Installation

Falasz needs Python 3.12 or newer on Linux or Windows. It has no dependencies.
**[docs/getting-started.md](docs/getting-started.md)** walks through installing on
Linux and Windows, a first program and a tour of the language.

The recommended way is [pipx](https://pipx.pypa.io/), which puts the `falasz`
command on your `PATH`:

```console
git clone https://github.com/legeng8901/falasz.git
pipx install ./falasz              # Windows: pipx install .\falasz
falasz --version
```

A built wheel installs the same way: `pipx install falasz-0.1.0a0-py3-none-any.whl`.

Into a virtual environment, inside the cloned `falasz` directory:

```console
python -m venv .venv
.venv/bin/pip install .            # Windows: .venv\Scripts\pip install .
```

`python -m falasz` works everywhere the `falasz` command does.

## Command line

| Command | What it does |
|---|---|
| `falasz run FILE` | checks the whole program (all modules), then runs it |
| `falasz run --sensors-mock DATA.json FILE` | runs with mock sensor data |
| `falasz run --max-steps N FILE` | stops with `LimitError` after N steps (useful for untrusted code and tests) |
| `falasz check FILE` | checks syntax, names, imports and exports of the program and all its modules **without running anything**; prints `OK` or every error |
| `falasz --version` | prints `falasz 0.1.0a0` |
| `falasz --debug run FILE` | as `run`, plus Python tracebacks for internal errors |

Program output goes to stdout as UTF-8 with `\n` line endings on every platform.
Diagnostics, warnings and tracebacks go to stderr.

| Exit code | Meaning |
|---|---|
| 0 | success |
| 1 | runtime error (the program started) |
| 2 | command-line usage error: bad arguments, missing input file, invalid `--sensors-mock` data |
| 3 | syntax, name, import or export error (nothing was run) |
| 70 | internal interpreter error (a bug, please report it); in 0.1 also when the computer runs out of memory, see [limitations](docs/limitations.md) |
| 130 | interrupted with Ctrl+C |

Errors always name the file, line and column (`falasz run error_trace.falasz`, run in `examples/`):

```text
Traceback:
  error_trace.falasz:15:7 in <main>
  error_trace.falasz:11:34 in report
  error_trace.falasz:7:18 in average
error_trace.falasz:7:18: ZeroDivisionError: division by zero
```

## The language in one page

The full, normative description is in [docs/spec.md](docs/spec.md) (in Polish).

* **Values:** `INTEGER` (up to 4300 digits), `FLOAT`, `STRING`, `BOOLEAN` (`TRUE`, `FALSE`),
  `NULL`, `LIST` (`[1, "a"]`), `MAP` (`{"key": 1}`), functions and modules.
* **No implicit conversions:** `"Age: " + 20` is a `TypeError`; use
  `STR`, `INT`, `FLOAT`. Conditions must be `BOOLEAN`. `/` always gives a `FLOAT`.
* **Variables:** `LET x = 1` declares, `x = 2` assigns. Only functions and modules
  have their own scope; `IF`/`WHILE`/`FOR` blocks do not. A variable exists once
  its `LET` has run.
* **Control flow:** `IF … ELSE IF … ELSE … END`, `WHILE … END`, `FOR x IN list/string/map … END`,
  `BREAK`, `CONTINUE`.
* **Functions:** `FUNC name(a, b) … RETURN value … END`; closures, recursion
  (up to 500 active calls), functions as values.
* **Output and builtins:** the `SAY value` statement; builtin functions `INPUT([prompt])`,
  `RANGE`, `STR`, `INT`, `FLOAT`, `LEN`.
* **Modules:** a file exports names with `EXPORT a, b`; another file uses
  `IMPORT LOCAL name` (or `IMPORT name`), then `name.a`. Local modules live next to
  the importing file; import cycles are reported before the program runs.
* **Standard library:** `files.read_text(path)`, `files.write_text(path, text)`
  (relative paths use the main script's directory), `sensors.available()`,
  `sensors.read(name)` (see [docs/sensors.md](docs/sensors.md)).

More programs are in [examples/](examples/): FizzBuzz, primes, statistics and a
grade report from standard input, a Caesar cipher, a temperature converter,
an inventory report, recursion, closures, a multi-file notes app, a monthly
budget from a CSV file, and a thermostat and a weather station driven by mock sensors.

## Safety notes

* Programs are interpreted from an AST. The interpreter never uses Python's
  `eval`/`exec` and never imports Python code from Falasz programs.
* There is no shell, network or process access in v0.1.
* `files` has the permissions of the process. **It is not a sandbox.** For untrusted
  programs, use OS-level isolation. `--max-steps` and the built-in limits (recursion
  depth, sizes) protect against runaway programs, not against malicious ones.
* No telemetry is collected.

## Development

```console
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

| Path | Contents |
|---|---|
| `src/falasz/` | lexer, parser, validator, module loader, interpreter, standard library, CLI |
| `tests/unit/` | unit tests per component |
| `tests/spec_examples/` | example programs from the specification with expected output or error position |
| `tests/test_cli.py` | end-to-end tests of the `falasz` command (real processes) |
| `tests/test_robustness.py` | random programs: must never crash the interpreter |
| `tests/test_docs.py` | the code in README and the getting started guide runs and prints what the text says |
| `examples/` | example programs with recorded output (`.out`), input (`.in`) and sensor data |
| `docs/` | getting started guide, specification, sensors API, limitations |
| `.github/workflows/ci.yml` | GitHub Actions: tests on Linux and Windows, Python 3.12–3.14, package install |

## License

Falasz is released under the [MIT License](LICENSE).
Copyright (c) 2026 Daniel Falasz.
