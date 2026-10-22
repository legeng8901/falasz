# Falasz — current limitations

State for **0.1.0a0** (after stage 7: CLI, packaging, CI workflow).

## Not verified yet

| Item | Where | Status |
|---|---|---|
| Verification on real Windows | CI | the GitHub Actions workflow is prepared but has never run; locally only Linux (Python 3.12, 3.13, 3.14) was tested |

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
- Very long `ELSE IF` chains (~200 branches) hit the nesting limit (N8).
- Nested values deeper than 500 levels cannot be printed or compared (`LimitError`).
- INTEGER <-> text conversion is limited to 4300 digits (Python's limit, `LimitError`).
- `files` is not a sandbox: `..` and absolute paths work with the process's
  permissions; resource limits do not replace OS-level isolation.
- Local modules must live in the importing file's directory (no subdirectories).
- `files` has only `read_text`/`write_text` (no listing, deleting, appending,
  existence check).
- Windows-specific path rules (drive-relative paths, device names) are unit-tested
  with `ntpath` on Linux only; real Windows runs come with CI in stage 7.
- At most 500 active user-function calls (`RecursionLimitError`); no tail-call optimisation.
- Closures created in a loop share the loop variable (loops have no scope, P6).
- Tree-walking interpreter: performance is not a goal of v0.1.
