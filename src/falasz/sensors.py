"""Sensor providers for the `sensors` module (docs/spec.md 9.4, docs/sensors.md).

The interpreter never talks to hardware directly; it asks a *provider*:

    available() -> list[str]          names of the sensors
    read(name)  -> int | float | bool | str

v0.1 ships two providers and no hardware adapters:
  - NullSensorProvider (default): no sensors at all;
  - MockSensorProvider: values from a dict or a JSON file, fully deterministic.

Providers are stateful (a mock sequence advances on every read), so each program
run should get a fresh provider.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Protocol

from .errors import FalaszSensorError
from .values import quote

SENSOR_NAME = re.compile(r"[A-Za-z0-9_.\-]{1,64}", re.ASCII)
MAX_SEQUENCE_LENGTH = 100_000
MAX_CONFIG_BYTES = 1024 * 1024

Reading = int | float | bool | str


class SensorConfigError(Exception):
    """Invalid mock configuration; raised before the program runs (CLI: usage error)."""


class SensorProvider(Protocol):
    def available(self) -> list[str]: ...

    def read(self, name: str) -> Reading: ...


def is_reading(value: Any) -> bool:
    """True for values a sensor may return: INTEGER, finite FLOAT, BOOLEAN, STRING."""
    t = type(value)
    return t is bool or t is int or t is str or (t is float and math.isfinite(value))


class NullSensorProvider:
    """No sensors (the default when no provider is configured)."""

    def available(self) -> list[str]:
        return []

    def read(self, name: str) -> Reading:
        raise FalaszSensorError(f"unknown sensor {quote(name)} (no sensors are available)")


class MockSensorProvider:
    """Deterministic sensors from configuration.

    Each value is either a constant reading (returned by every read) or a
    non-empty list of readings (returned one per read; reading past the end is
    a SensorError).
    """

    def __init__(self, config: dict[str, Any]):
        self._constants: dict[str, Reading] = {}
        self._sequences: dict[str, list[Reading]] = {}
        self._positions: dict[str, int] = {}
        if type(config) is not dict:
            raise SensorConfigError(f"mock configuration must be an object/dict, not {type(config).__name__}")
        for name, value in config.items():
            if type(name) is not str or not SENSOR_NAME.fullmatch(name):
                raise SensorConfigError(
                    f"invalid sensor name {name!r}: use 1-64 ASCII letters, digits, '_', '.' or '-'"
                )
            if type(value) is list:
                if not value:
                    raise SensorConfigError(f"sensor {name!r}: a sequence must not be empty")
                if len(value) > MAX_SEQUENCE_LENGTH:
                    raise SensorConfigError(f"sensor {name!r}: sequence longer than {MAX_SEQUENCE_LENGTH}")
                for i, item in enumerate(value):
                    _check_reading(f"{name}[{i}]", item)
                self._sequences[name] = list(value)
                self._positions[name] = 0
            else:
                _check_reading(name, value)
                self._constants[name] = value

    @classmethod
    def from_json_text(cls, text: str, source: str = "<json>") -> MockSensorProvider:
        try:
            config = json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)
        except json.JSONDecodeError as exc:
            raise SensorConfigError(f"{source}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}") from None
        except (SensorConfigError, ValueError) as exc:
            raise SensorConfigError(f"{source}: {exc}") from None
        try:
            return cls(config)
        except SensorConfigError as exc:
            raise SensorConfigError(f"{source}: {exc}") from None

    @classmethod
    def from_json_file(cls, path: str) -> MockSensorProvider:
        try:
            with open(path, "rb") as f:
                data = f.read(MAX_CONFIG_BYTES + 1)
        except OSError as exc:
            raise SensorConfigError(f"cannot read sensor mock file {path!r}: {exc.strerror}") from None
        if len(data) > MAX_CONFIG_BYTES:
            raise SensorConfigError(f"{path}: sensor mock file is larger than {MAX_CONFIG_BYTES} bytes")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SensorConfigError(f"{path}: not valid UTF-8 (byte offset {exc.start})") from None
        return cls.from_json_text(text, path)

    def available(self) -> list[str]:
        return sorted([*self._constants, *self._sequences])

    def read(self, name: str) -> Reading:
        if name in self._constants:
            return self._constants[name]
        if name in self._sequences:
            sequence = self._sequences[name]
            position = self._positions[name]
            if position >= len(sequence):
                raise FalaszSensorError(
                    f"sensor {quote(name)} has no more readings (all {len(sequence)} were used)"
                )
            self._positions[name] = position + 1
            return sequence[position]
        names = self.available()
        shown = ", ".join(names[:10]) + (", ..." if len(names) > 10 else "")
        raise FalaszSensorError(f"unknown sensor {quote(name)} (available: {shown or 'none'})")


_JSON_NAMES = {type(None): "null", list: "a nested array", dict: "an object"}


def _check_reading(where: str, value: Any) -> None:
    if not is_reading(value):
        if type(value) is float:
            problem = "a non-finite float"
        else:
            problem = _JSON_NAMES.get(type(value), type(value).__name__)
        raise SensorConfigError(
            f"sensor {where!r}: value must be an integer, finite float, boolean or string, not {problem}"
        )


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SensorConfigError(f"duplicate sensor name {key!r}")
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise SensorConfigError(f"{name} is not allowed (readings must be finite)")
