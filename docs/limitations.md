# Falasz — current limitations

State for **0.1.0a0** (release preparation).

## Verification status

| Item | Status |
|---|---|
| Linux, Python 3.12 / 3.13 / 3.14 | full test suite passes locally and in GitHub Actions (Ubuntu 24.04) |
| Windows, Python 3.12 / 3.13 / 3.14 | full test suite passes in GitHub Actions (Windows Server 2025); 5 POSIX-only tests are skipped there |
| Ubuntu 26.04 (next `ubuntu-latest`) | full test suite passes locally in a container; not yet in GitHub Actions |
| `falasz` on `PATH` after `pipx install` | verified locally on Linux; the Windows check is in the CI workflow but has not run yet |

## Outside v0.1 (decided)

`TRY/CATCH`, lambdas, list methods (`APPEND` etc.), string interpolation,
exponent notation (`1e5`), compiler.

## Known language gaps found while writing examples

Planned after v0.1 (spec section 13): `HAS(map, key)`, `APPEND(list, value)`, `TYPE(value)`, and an optional
`files` directory restriction (`--files-root`; an access limit, not a sandbox).

- No way to test whether a MAP contains a key without iterating its keys
  (`m[k]` on a missing key is a `KeyError`). See `examples/word_count.falasz`.
- No way to add to a LIST other than `xs = xs + [x]` (creates a new list each time,
  O(n) per append).
- No string functions (split, upper, slicing) besides indexing and `LEN`.
- String escapes are only `\"`, `\\`, `\n`, `\t`: a carriage return (`\r`) or
  other control character cannot be written in a literal. Text read from a file
  with Windows line endings contains `\r`; it can be filtered out only by
  comparison (`ch < " "`), see `examples/budget/csv.falasz`. A `\r` escape is
  planned for v0.2.
- No rounding function: a FLOAT is printed with all its digits
  (`37.77777777777778`); rounding has to be written by hand
  (`examples/temperature.falasz`).
- No way to ask for the type of a value (no `TYPE()`); code that handles mixed
  values has to inspect `STR(x)`.

## Sensors

- No real hardware: only the `null` (default) and `mock` providers exist; see
  [sensors.md](sensors.md).
- A program cannot ask whether a sequence sensor has readings left; reading past
  the end is a `SensorError`, so programs need a known count.
- Readings have no timestamps or units.

## Implementation limits

- One syntax error per file is reported (parser stops at the first one, N7).
- A statement ends at the end of its line; an expression continues on the next
  line only inside `( )`, `[ ]` or `{ }`.
- Very long `ELSE IF` chains (~200 branches) hit the nesting limit (N8).
- Nested values deeper than 500 levels cannot be printed or compared (`LimitError`).
- INTEGER values have at most 4300 decimal digits: a `+`, `-` or `*` whose result
  would be larger is a `LimitError`. It is the same limit as for converting an
  INTEGER to or from text, so every INTEGER can be printed.
- `files` is not a sandbox: `..` and absolute paths work with the process's
  permissions; resource limits do not replace OS-level isolation.
- Local modules must live in the importing file's directory (no subdirectories).
- `files` has only `read_text`/`write_text` (no listing, deleting, appending,
  existence check).
- Windows-specific path rules (drive-relative paths, device names) are unit-tested
  with `ntpath` and also run on real Windows in CI.
- At most 500 active user-function calls (`RecursionLimitError`); no tail-call optimisation.
- Closures created in a loop share the loop variable (loops have no scope, P6).
- Tree-walking interpreter: performance is not a goal of v0.1.

## Resource limits that do not exist yet

The limits above stop runaway programs; they do not bound memory. Untrusted
programs need OS-level limits (memory, time).

- No memory limit. A program that keeps doubling a STRING or LIST runs until
  the operating system refuses more memory. **Current behaviour (kept in 0.1):**
  the interpreter stops with `InternalError: MemoryError` and exit code 70, and
  its message calls this a bug, although it is not one. Reporting it as an
  ordinary program error is planned for v0.2.
- `INPUT()` reads a whole line however long it is.
- `files.read_text` on a named pipe (FIFO) waits until another process writes to
  it.
