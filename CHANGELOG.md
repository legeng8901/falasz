# Changelog

All notable changes to Falasz are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[PEP 440](https://peps.python.org/pep-0440/).

## [0.1.0a0] - unreleased

First alpha of the language and its reference interpreter.

### Language
- Specification v0.1 ([docs/spec.md](docs/spec.md)): grammar (EBNF), operator
  precedence, types, scopes, diagnostics, limits; owner decisions P1–P16,
  N1–N8 and E1–E25 recorded in section 12.
- Types INTEGER (arbitrary precision), FLOAT, STRING, BOOLEAN, NULL, LIST, MAP;
  functions and modules as values.
- Strict typing without implicit conversions; `/` always returns FLOAT;
  conditions and `AND`/`OR`/`NOT` require BOOLEAN; short-circuit evaluation.
- `LET`, assignment, `IF`/`ELSE IF`/`ELSE`, `WHILE`, `FOR … IN` (lists, strings,
  maps), `BREAK`, `CONTINUE`, `SAY`.
- Function and module scopes only; static name resolution; a variable exists
  only after its declaration ran.
- User functions with closures, recursion (limit 500 active calls) and
  call-stack traces.
- Builtins `RANGE`, `STR`, `INT`, `FLOAT`, `LEN`, `INPUT`.
- Modules: `IMPORT [LOCAL] name [AS alias]`, explicit `EXPORT`, static import
  cycle detection, export checks, read-only live exports.
- Standard library: `files.read_text`/`files.write_text` (UTF-8, no newline
  translation, paths relative to the main script); `sensors.available`/
  `sensors.read` with `null` and `mock` providers.

### Tooling
- `falasz run`, `falasz check`, `falasz --version`; options `--sensors-mock`,
  `--max-steps`, `--debug`; exit codes 0/1/2/3/70/130.
- Diagnostics with file, line and column; all syntax-valid name errors of all
  modules reported at once; warnings for shadowed standard modules.
- Python package with the `falasz` console script and `python -m falasz`.
- GitHub Actions workflow for Linux and Windows (prepared, not yet run).
- Released under the MIT License; author metadata in the package.

### Documentation and examples
- Getting started guide for Linux and Windows
  ([docs/getting-started.md](docs/getting-started.md)); installation with pipx
  so that `falasz` is on `PATH`.
- New examples: Caesar cipher, grade report from standard input, temperature
  converter, monthly budget from a CSV file (modules + files).
- The code in README and the guide is run by the test suite.

### Fixed before release
- A source file is read only up to the 1 MiB limit: `falasz check /dev/zero`
  or a huge module now gives `LimitError` (exit code 3) instead of running out
  of memory and reporting an internal error.

### Known limitations
- See [docs/limitations.md](docs/limitations.md). Planned after v0.1:
  `HAS`, `APPEND`, `TYPE`, an optional `files` directory restriction.
