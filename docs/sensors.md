# `sensors` module — API reference (v0.1)

The `sensors` module lets Falasz programs read named sensor values. In v0.1 the
values always come from a **provider** configured by whoever runs the program.
Real hardware is not supported: the only providers are `null` (default) and
`mock` (deterministic values for tests and demos).

```falasz
IMPORT sensors

SAY sensors.available()              # ["door_open", "temperature"]
LET t = sensors.read("temperature")  # 21.5
IF sensors.read("door_open")
    SAY "close the door"
END
```

## Functions

### `sensors.available()` → LIST of STRING

Returns a **new** list with the sensor names, sorted by Unicode code point
(`"A" < "B" < "a"`). It does not consume readings. Without a provider it returns `[]`.

| Error | When |
|---|---|
| `ArityError` | called with arguments |
| `SensorError` | the provider failed or returned something that is not a list of names |

### `sensors.read(name)` → INTEGER, FLOAT, BOOLEAN or STRING

Returns the next reading of the sensor `name`. Names are compared exactly:
`"Temperature"` and `" temperature"` are different from `"temperature"`.

| Error | When |
|---|---|
| `TypeError` | `name` is not a STRING |
| `ArityError` | not exactly one argument |
| `SensorError` | unknown sensor; the message lists up to 10 available names |
| `SensorError` | a sequence sensor has no more readings |
| `SensorError` | the provider failed, or returned NULL, NaN/infinity, a list, … |

Errors point at the `(` of the `sensors.read(...)` call and, inside functions, come
with a call-stack trace like every other runtime error.

## Mock data

A mock configuration is a JSON object (or a Python `dict` in the API) that maps
sensor names to values:

```json
{
  "temperature": [19.5, 20.0, 21.5],
  "humidity": 40,
  "door_open": false,
  "location": "kitchen"
}
```

* **Constant value** — returned by every `read`: an integer (`40` → INTEGER), a
  finite number with a decimal point (`40.0` → FLOAT), `true`/`false` (BOOLEAN) or
  a string.
* **Sequence** — a non-empty array of such values (they may mix types). Each `read`
  returns the next element; once all are used, every further `read` of that sensor
  is a `SensorError`. The sensor is still listed by `available()`. Each sensor has
  its own position.
* **Names** — 1 to 64 ASCII characters from `A-Z a-z 0-9 _ . -`.

Rejected **before the program starts** (configuration error; the CLI will exit with
code 2):

| Problem | Example |
|---|---|
| invalid JSON (message has line and column; the exact text and column come from Python's `json` module and can differ slightly between Python versions) | `{"a": 1,}` |
| top level is not an object | `[1, 2]` |
| invalid name | `{"temp erature": 1}`, `{"": 1}` |
| duplicate name | `{"a": 1, "a": 2}` |
| `null`, nested arrays, objects | `{"a": null}`, `{"a": [[1]]}`, `{"a": {}}` |
| empty sequence | `{"a": []}` |
| non-finite numbers | `NaN`, `Infinity`, `1e400` |
| more than 100 000 readings in one sequence | |
| file larger than 1 MiB, not UTF-8 (a BOM is fine), unreadable | |

## Determinism

A mock provider is **stateful**: sequences advance with every read. Running a
program with a fresh provider built from the same data always gives the same
result. Reusing one provider object for a second run continues where the first
run stopped.

## Python API

```python
from falasz.runtime import run_file
from falasz.sensors import MockSensorProvider, SensorConfigError

provider = MockSensorProvider.from_json_file("sensors.json")    # or MockSensorProvider({...})
run_file("program.falasz", sensors=provider)
```

| Name | Purpose |
|---|---|
| `MockSensorProvider(config: dict)` | provider from a dict; validates like JSON |
| `MockSensorProvider.from_json_text(text, source="<json>")` | provider from JSON text |
| `MockSensorProvider.from_json_file(path)` | provider from a JSON file |
| `NullSensorProvider()` | no sensors (the default) |
| `SensorConfigError` | raised for invalid mock data |

### Writing a provider (future hardware adapters)

Any object with these two methods can be passed as `sensors=`:

```python
class MyProvider:
    def available(self) -> list[str]: ...
    def read(self, name: str) -> int | float | bool | str: ...
```

The interpreter validates everything a provider returns and turns any exception
it raises into a `SensorError`, so a faulty adapter cannot crash the interpreter.
`read` should raise `falasz.errors.FalaszSensorError` for unknown or exhausted
sensors to control the message.

## Not in v0.1

* real sensors / hardware adapters;
* timestamps, units or metadata for readings;
* a way to check whether a sequence has readings left (use a known count).
