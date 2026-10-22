# Falasz — current limitations

State after **stage 4** (user functions). Updated at every stage.

## Not implemented yet (planned for v0.1)

| Feature | Stage | Current behaviour |
|---|---|---|
| `IMPORT` / module loading, `module.member`, export checks across files, `files` | 5 | `IMPORT` raises `NotImplementedError` (temporary category) at run time; `m.x` raises `TypeError` |
| `sensors` (mock provider) | 6 | not available |
| `falasz` command (`run`, `check`, `--version`), exit codes, `--max-steps`, `--sensors-mock`, warnings | 7 | only the Python API exists: `falasz.runtime.run_source` / `check_source` |
| Windows verification (CI) | 7 | tested only on Linux (Fedora, Python 3.14) |

## Outside v0.1 (decided)

`TRY/CATCH`, lambdas, list methods (`APPEND` etc.), string interpolation,
exponent notation (`1e5`), compiler.

## Known language gaps found while writing examples

Planned after v0.1 (spec section 13): `HAS(map, key)`, `APPEND(list, value)`, `TYPE(value)`.

- No way to test whether a MAP contains a key without iterating its keys
  (`m[k]` on a missing key is a `KeyError`). See `examples/word_count.falasz`.
- No way to add to a LIST other than `xs = xs + [x]` (creates a new list each time,
  O(n) per append).
- No string functions (split, upper, slicing) besides indexing and `LEN`.
- No way to ask for the type of a value (no `TYPE()`); code that handles mixed
  values has to inspect `STR(x)`.

## Implementation limits

- One syntax error per file is reported (parser stops at the first one, N7).
- Very long `ELSE IF` chains (~200 branches) hit the nesting limit (N8).
- Nested values deeper than 500 levels cannot be printed or compared (`LimitError`).
- INTEGER <-> text conversion is limited to 4300 digits (Python's limit, `LimitError`).
- `files` is not a sandbox (applies from stage 5); resource limits do not replace
  OS-level isolation.
- At most 500 active user-function calls (`RecursionLimitError`); no tail-call optimisation.
- Closures created in a loop share the loop variable (loops have no scope, P6).
- Tree-walking interpreter: performance is not a goal of v0.1.
