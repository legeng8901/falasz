"""Stage 6: the `sensors` module with deterministic providers (no hardware involved)."""

import io
import json

import pytest

from falasz.errors import FalaszError
from falasz.interpreter import Interpreter
from falasz.runtime import StaticErrors, run_source
from falasz.sensors import (
    MAX_CONFIG_BYTES,
    MockSensorProvider,
    NullSensorProvider,
    SensorConfigError,
)

CONFIG = {
    "temperature": 21.5,
    "humidity": 40,
    "door_open": False,
    "location": "kitchen",
    "steps": [1, 2, 3],
}


def run(body, sensors=None, config=CONFIG):
    if sensors is None and config is not None:
        sensors = MockSensorProvider(config)
    out = io.StringIO()
    run_source("IMPORT sensors\n" + body, "t.falasz", out=out, sensors=sensors)
    return out.getvalue()


def fail(body, sensors=None, config=CONFIG):
    with pytest.raises((FalaszError, StaticErrors)) as exc:
        run(body, sensors, config)
    err = exc.value.errors[0] if isinstance(exc.value, StaticErrors) else exc.value
    return err


# ============================================================ default


def test_default_provider_has_no_sensors():
    assert run("SAY sensors.available()\n", config=None) == "[]\n"
    err = fail('SAY sensors.read("temperature")\n', config=None)
    assert err.category == "SensorError"
    assert err.message == 'unknown sensor "temperature" (no sensors are available)'


def test_interpreter_default_is_null_provider():
    assert isinstance(Interpreter("t.falasz").sensors, NullSensorProvider)


# ======================================================= reading values


def test_available_is_sorted_by_code_point():
    provider = MockSensorProvider({"b": 1, "A": 1, "a": 1, "_x": 1, "B.2": 1, "1": 1})
    assert run("SAY sensors.available()\n", provider) == '["1", "A", "B.2", "_x", "a", "b"]\n'


def test_constant_readings_keep_their_types():
    body = ('SAY sensors.read("temperature") + 0.5\n'
            'SAY sensors.read("humidity") * 2\n'
            'SAY sensors.read("humidity") / 8\n'
            'SAY NOT sensors.read("door_open")\n'
            'SAY "in " + sensors.read("location")\n')
    assert run(body) == "22.0\n80\n5.0\nTRUE\nin kitchen\n"


def test_constant_reading_repeats():
    assert run('FOR i IN RANGE(0, 3)\n    SAY sensors.read("humidity")\nEND\n') == "40\n40\n40\n"


def test_integer_and_float_are_distinct():
    provider = MockSensorProvider({"i": 21, "f": 21.0})
    assert run('SAY sensors.read("i")\nSAY sensors.read("f")\nSAY sensors.read("i") == sensors.read("f")\n',
               provider) == "21\n21.0\nTRUE\n"


def test_boolean_reading_drives_if():
    body = 'IF sensors.read("door_open")\n    SAY "open"\nELSE\n    SAY "closed"\nEND\n'
    assert run(body) == "closed\n"


def test_sequence_returns_readings_in_order():
    body = 'FOR i IN RANGE(0, 3)\n    SAY sensors.read("steps")\nEND\n'
    assert run(body) == "1\n2\n3\n"


def test_sequence_exhaustion_is_sensor_error_at_call():
    body = 'FOR i IN RANGE(0, 4)\n    SAY sensors.read("steps")\nEND\n'
    err = fail(body)
    assert (err.category, err.pos.line, err.pos.column) == ("SensorError", 3, 21)
    assert err.message == 'sensor "steps" has no more readings (all 3 were used)'


def test_exhausted_sequence_stays_exhausted_and_listed():
    provider = MockSensorProvider({"once": [7]})
    assert run('SAY sensors.read("once")\nSAY sensors.available()\n', provider) == '7\n["once"]\n'
    with pytest.raises(FalaszError):
        provider.read("once")
    assert provider.available() == ["once"]


def test_sequences_are_independent_per_sensor():
    provider = MockSensorProvider({"a": [1, 2], "b": [10, 20]})
    body = 'SAY sensors.read("a")\nSAY sensors.read("b")\nSAY sensors.read("a")\nSAY sensors.read("b")\n'
    assert run(body, provider) == "1\n10\n2\n20\n"


def test_sequence_with_mixed_types():
    provider = MockSensorProvider({"status": ["ok", 3, 2.5, True]})
    body = 'FOR i IN RANGE(0, 4)\n    SAY sensors.read("status")\nEND\n'
    assert run(body, provider) == "ok\n3\n2.5\nTRUE\n"


def test_available_does_not_consume_readings():
    body = 'LET a = sensors.available()\nLET b = sensors.available()\nSAY sensors.read("steps")\n'
    assert run(body) == "1\n"


def test_available_returns_a_new_list_each_time():
    body = 'LET a = sensors.available()\na[0] = "changed"\nSAY sensors.available()[0]\n'
    assert run(body) == "door_open\n"


def test_fresh_providers_give_identical_runs():
    body = 'FOR i IN RANGE(0, 3)\n    SAY sensors.read("steps")\nEND\nSAY sensors.available()\n'
    first = run(body, MockSensorProvider(CONFIG))
    second = run(body, MockSensorProvider(CONFIG))
    assert first == second == '1\n2\n3\n["door_open", "humidity", "location", "steps", "temperature"]\n'


def test_reusing_a_provider_continues_its_sequences():
    # Documented behaviour: providers are stateful; use a fresh one per run.
    provider = MockSensorProvider({"s": [1, 2]})
    assert run('SAY sensors.read("s")\n', provider) == "1\n"
    assert run('SAY sensors.read("s")\n', provider) == "2\n"


def test_config_dict_is_copied():
    config = {"s": [1, 2], "c": 5}
    provider = MockSensorProvider(config)
    config["s"].append(3)
    config["c"] = 6
    assert run('SAY sensors.read("c")\nSAY sensors.available()\n', provider) == '5\n["c", "s"]\n'


def test_sensors_in_module_function_and_traceback(tmp_path):
    (tmp_path / "probe.falasz").write_text(
        'EXPORT probe\nIMPORT sensors\nFUNC probe(n)\n    RETURN sensors.read(n)\nEND\n', encoding="utf-8")
    main = tmp_path / "main.falasz"
    main.write_text('IMPORT LOCAL probe\nSAY probe.probe("humidity")\nSAY probe.probe("nope")\n', encoding="utf-8")
    out = io.StringIO()
    with pytest.raises(FalaszError) as exc:
        run_source(None, str(main), out=out, sensors=MockSensorProvider(CONFIG))
    assert out.getvalue() == "40\n"
    err = exc.value
    assert (err.category, err.path, err.pos.line, err.pos.column) == ("SensorError", "probe.falasz", 4, 24)
    assert [e.name for e in err.trace] == ["<main>", "probe"]


# ================================================================ errors


def test_unknown_sensor_lists_available():
    err = fail('SAY sensors.read("pressure")\n')
    assert (err.category, err.pos.line, err.pos.column) == ("SensorError", 2, 17)
    assert err.message == ('unknown sensor "pressure" '
                           "(available: door_open, humidity, location, steps, temperature)")


def test_unknown_sensor_list_is_truncated():
    provider = MockSensorProvider({f"s{i:02}": i for i in range(15)})
    err = fail('SAY sensors.read("x")\n', provider)
    assert err.message.endswith("s08, s09, ...)")


@pytest.mark.parametrize("name", ['""', '"Temperature"', '" temperature"', '"temperature "'])
def test_names_are_exact(name):
    assert fail(f"SAY sensors.read({name})\n").category == "SensorError"


@pytest.mark.parametrize("arg, kind", [("1", "INTEGER"), ("NULL", "NULL"), ('["temperature"]', "LIST"), ("TRUE", "BOOLEAN")])
def test_read_argument_must_be_string(arg, kind):
    err = fail(f"SAY sensors.read({arg})\n")
    assert err.category == "TypeError"
    assert err.message == f"sensors.read: name must be STRING, not {kind}"


@pytest.mark.parametrize("call, message", [
    ("sensors.read()", "sensors.read expects 1 argument(s), got 0"),
    ('sensors.read("a", "b")', "sensors.read expects 1 argument(s), got 2"),
    ('sensors.available("x")', "sensors.available expects 0 argument(s), got 1"),
])
def test_arity(call, message):
    err = fail(f"SAY {call}\n")
    assert err.category == "ArityError" and err.message == message


def test_unknown_member_is_static_error():
    err = fail("SAY sensors.write(1)\n")
    assert (err.category, err.message) == ("NameError", "module 'sensors' does not export 'write'")


# ================================================ provider failures


class Broken:
    def __init__(self, available=None, value=None, exc=None):
        self._available, self._value, self._exc = available, value, exc

    def available(self):
        if self._exc:
            raise self._exc
        return self._available

    def read(self, name):
        if self._exc:
            raise self._exc
        return self._value


def test_provider_exception_becomes_sensor_error():
    err = fail('SAY sensors.read("x")\n', Broken(exc=OSError("I2C bus timeout")))
    assert (err.category, err.message) == ("SensorError", 'sensor "x" failed: I2C bus timeout')
    err = fail("SAY sensors.available()\n", Broken(exc=RuntimeError("driver crashed")))
    assert (err.category, err.message) == ("SensorError", "sensor provider failed to list sensors: driver crashed")


@pytest.mark.parametrize("value, shown", [
    (None, "NoneType"), (float("nan"), "float"), (float("inf"), "float"), ([1], "list"),
    ({"a": 1}, "dict"), (b"raw", "bytes"), ((1, 2), "tuple"),
])
def test_invalid_provider_values_are_rejected(value, shown):
    err = fail('SAY sensors.read("x")\n', Broken(value=value))
    assert err.category == "SensorError"
    assert err.message == f'sensor "x" returned an invalid value ({shown})'


@pytest.mark.parametrize("names", [None, ("a",), ["a", 1], "abc"])
def test_invalid_provider_name_lists_are_rejected(names):
    err = fail("SAY sensors.available()\n", Broken(available=names))
    assert err.category == "SensorError" and "invalid list of sensor names" in err.message


def test_custom_provider_implements_the_protocol():
    class Clock:
        def __init__(self):
            self.ticks = 0

        def available(self):
            return ["ticks"]

        def read(self, name):
            self.ticks += 1
            return self.ticks

    body = 'SAY sensors.read("ticks") + sensors.read("ticks")\nSAY sensors.available()\n'
    assert run(body, Clock()) == '3\n["ticks"]\n'


def test_provider_names_are_sorted_for_determinism():
    assert run("SAY sensors.available()\n", Broken(available=["z", "a"])) == '["a", "z"]\n'


# ===================================================== config validation


@pytest.mark.parametrize("name", ["", " ", "temp erature", "żar", "a/b", "x" * 65, "tab\t", 5, None])
def test_invalid_sensor_names(name):
    with pytest.raises(SensorConfigError, match="invalid sensor name"):
        MockSensorProvider({name: 1})


@pytest.mark.parametrize("name", ["a", "A1", "temp.inside", "door-1", "_x", "x" * 64])
def test_valid_sensor_names(name):
    assert MockSensorProvider({name: 1}).available() == [name]


@pytest.mark.parametrize("value, fragment", [
    (None, "not null"), ([[1]], "not a nested array"), ({"a": 1}, "not an object"),
    ([], "must not be empty"), (float("nan"), "non-finite"), (float("-inf"), "non-finite"),
    ([1, None], "'s[1]'"), (b"x", "not bytes"), ((1,), "not tuple"),
])
def test_invalid_values(value, fragment):
    with pytest.raises(SensorConfigError) as exc:
        MockSensorProvider({"s": value})
    assert fragment in str(exc.value)


def test_config_must_be_a_mapping():
    with pytest.raises(SensorConfigError, match="must be an object"):
        MockSensorProvider([1, 2])


def test_sequence_length_limit(monkeypatch):
    from falasz import sensors
    monkeypatch.setattr(sensors, "MAX_SEQUENCE_LENGTH", 3)
    MockSensorProvider({"s": [1, 2, 3]})
    with pytest.raises(SensorConfigError, match="longer than 3"):
        MockSensorProvider({"s": [1, 2, 3, 4]})


def test_empty_config_is_valid():
    assert MockSensorProvider({}).available() == []


# ============================================================== JSON


def test_json_types_map_to_falasz_types():
    provider = MockSensorProvider.from_json_text(
        '{"i": 21, "f": 21.0, "neg": -3.5, "b": true, "s": "x", "seq": [1, "two", false], '
        '"big": 123456789012345678901234567890}')
    body = ('SAY sensors.read("i")\nSAY sensors.read("f")\nSAY sensors.read("neg")\nSAY sensors.read("b")\n'
            'SAY sensors.read("s")\nSAY sensors.read("seq")\nSAY sensors.read("seq")\nSAY sensors.read("big")\n')
    assert run(body, provider) == "21\n21.0\n-3.5\nTRUE\nx\n1\ntwo\n123456789012345678901234567890\n"


@pytest.mark.parametrize("text, fragment", [
    ('{"a": 1, "a": 2}', "duplicate sensor name 'a'"),
    ('{"a": NaN}', "NaN is not allowed"),
    ('{"a": Infinity}', "Infinity is not allowed"),
    ('{"a": -Infinity}', "-Infinity is not allowed"),
    ('{"a": 1e400}', "non-finite"),
    ('[1, 2]', "must be an object"),
    ('{"a": null}', "not null"),
    ('{"a": {"b": 1}}', "not an object"),
    ('{"a": [[1]]}', "not a nested array"),
    ('{"a": []}', "must not be empty"),
    ('{"a b": 1}', "invalid sensor name"),
    # Position/text come from Python's json module and differ between versions
    # (3.12: column 9, 3.13+: column 8 at the comma), so only the line is fixed.
    ('{"a": 1,}', "<json>:1:"),
    ('{\n  "a": 1\n  "b": 2\n}', "<json>:3:3: invalid JSON"),
    ("", "invalid JSON"),
    ('{"a": ' + "1" * 5000 + "}", "<json>:"),
])
def test_invalid_json(text, fragment):
    with pytest.raises(SensorConfigError) as exc:
        MockSensorProvider.from_json_text(text)
    assert fragment in str(exc.value)


def test_json_file(tmp_path):
    path = tmp_path / "sensors.json"
    path.write_text(json.dumps({"t": [20.5, 21.0]}), encoding="utf-8")
    provider = MockSensorProvider.from_json_file(str(path))
    assert run('SAY sensors.read("t")\nSAY sensors.read("t")\n', provider) == "20.5\n21.0\n"


def test_json_file_with_bom(tmp_path):
    path = tmp_path / "bom.json"
    path.write_bytes(b'\xef\xbb\xbf{"a": 1}')
    assert MockSensorProvider.from_json_file(str(path)).available() == ["a"]


def test_json_file_errors_name_the_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"a": null}', encoding="utf-8")
    with pytest.raises(SensorConfigError, match="bad.json: sensor 'a'"):
        MockSensorProvider.from_json_file(str(bad))
    binary = tmp_path / "bin.json"
    binary.write_bytes(b'{"a": "\xff"}')
    with pytest.raises(SensorConfigError, match="not valid UTF-8"):
        MockSensorProvider.from_json_file(str(binary))
    with pytest.raises(SensorConfigError, match="cannot read sensor mock file"):
        MockSensorProvider.from_json_file(str(tmp_path / "missing.json"))
    with pytest.raises(SensorConfigError, match="cannot read sensor mock file"):
        MockSensorProvider.from_json_file(str(tmp_path))


def test_json_file_size_limit(tmp_path, monkeypatch):
    from falasz import sensors
    monkeypatch.setattr(sensors, "MAX_CONFIG_BYTES", 16)
    path = tmp_path / "big.json"
    path.write_text('{"a": "' + "x" * 20 + '"}', encoding="utf-8")
    with pytest.raises(SensorConfigError, match="larger than 16 bytes"):
        MockSensorProvider.from_json_file(str(path))
    assert MAX_CONFIG_BYTES == 1024 * 1024
