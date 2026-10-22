"""Random programs must only ever fail with Falasz errors, never raw Python exceptions."""

import io
import random

import pytest

from falasz.errors import FalaszError
from falasz.runtime import StaticErrors, run_source
from falasz.sensors import MockSensorProvider

FRAGMENTS = [
    "LET", "SAY", "IF", "ELSE", "WHILE", "FOR", "IN", "FUNC", "RETURN", "END", "BREAK",
    "CONTINUE", "IMPORT", "LOCAL", "AS", "EXPORT", "TRUE", "FALSE", "NULL", "AND", "OR", "NOT",
    "x", "y", "LEN", "STR", "INT", "FLOAT", "RANGE", "INPUT", "0", "1", "-", "2.5", '"s"', '"\\n"',
    "+", "*", "/", "%", "==", "!=", "<", ">=", "=", "(", ")", "[", "]", "{", "}", ",", ".", ":",
    "\n", "\n", "\n", "#c", "9" * 30, "0.1",
]

PROGRAMS = [
    "LET x = {}\nLET y = [x, 1, \"a\"]\n",
    "LET x = 0\nLET y = RANGE(0, 5)\n",
]


def random_source(rng):
    prefix = rng.choice(PROGRAMS)
    return prefix + " ".join(rng.choice(FRAGMENTS) for _ in range(rng.randint(1, 25)))


@pytest.mark.parametrize("seed", range(40))
def test_random_programs_fail_cleanly(seed):
    rng = random.Random(seed)
    for _ in range(100):
        src = random_source(rng)
        try:
            run_source(src, "fuzz.falasz", out=io.StringIO(), inp=io.BytesIO(b"1\n"), max_steps=5000)
        except (FalaszError, StaticErrors) as err:
            errors = err.errors if isinstance(err, StaticErrors) else [err]
            for e in errors:
                assert e.path == "fuzz.falasz" and e.pos is not None, (src, e)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"raw {type(exc).__name__}: {exc}\nsource:\n{src}")


ATOMS = ["0", "1", "-3", "2.5", "0.0", '"a"', '""', "TRUE", "FALSE", "NULL", "[]", '[1, "a"]',
         '{"k": 1}', "{}", "x", "y", "LEN", 'RANGE(0, 3)', 'INT("5")', "INPUT()", "9" * 25,
         "h", "h(x)", "r(3)", "r(y)", "make()", "make()(1)",
         'sensors.read("s")', 'sensors.read("c")', "sensors.available()", 'sensors.read("x")']
BINARY_OPS = ["+", "-", "*", "/", "%", "==", "!=", "<", ">=", "AND", "OR"]


def random_expr(rng, depth=0):
    roll = rng.random()
    if depth > 4 or roll < 0.3:
        return rng.choice(ATOMS)
    if roll < 0.7:
        return f"({random_expr(rng, depth + 1)} {rng.choice(BINARY_OPS)} {random_expr(rng, depth + 1)})"
    if roll < 0.78:
        return f"(NOT {random_expr(rng, depth + 1)})"  # NOT binds looser than + and -
    if roll < 0.84:
        return f"-{random_expr(rng, depth + 1)}"
    if roll < 0.9:
        return f"{random_expr(rng, depth + 1)}[{random_expr(rng, depth + 1)}]"
    if roll < 0.95:
        return f"[{random_expr(rng, depth + 1)}, {random_expr(rng, depth + 1)}]"
    return f"{rng.choice(['LEN', 'STR', 'INT', 'FLOAT'])}({random_expr(rng, depth + 1)})"


def random_statement(rng):
    e = lambda: random_expr(rng)  # noqa: E731
    return rng.choice([
        lambda: f"SAY {e()}",
        lambda: f"x = {e()}",
        lambda: f"y[{e()}] = {e()}",
        lambda: f"IF {e()}\n SAY 1\nELSE\n SAY 2\nEND",
        lambda: f"FOR z IN {e()}\n SAY z\nEND",
        lambda: f"WHILE {e()}\n BREAK\nEND",
        lambda: f"SAY h({e()})",
        lambda: f"SAY r({e()})",
        lambda: f"SAY {e()}({e()})",
    ])()


FUNCTIONS = """IMPORT sensors
FUNC h(p)
    RETURN p
END
FUNC r(n)
    IF n <= 0
        RETURN [n]
    END
    RETURN r(n - 1) + [n]
END
FUNC make()
    FUNC inner(v)
        x = v
        RETURN x
    END
    RETURN inner
END
"""


@pytest.mark.parametrize("seed", range(40))
def test_random_well_formed_programs_fail_cleanly(seed):
    rng = random.Random(1000 + seed)
    for _ in range(50):
        body = "\n".join(random_statement(rng) for _ in range(rng.randint(1, 6)))
        src = 'LET x = [1, 2]\nLET y = {"k": [0]}\n' + FUNCTIONS + body + "\n"
        try:
            sensors = MockSensorProvider({"s": [1, "a", 2.5, True, 0], "c": -3})
            run_source(src, "fuzz.falasz", out=io.StringIO(), inp=io.BytesIO(b"7\n"), max_steps=5000,
                       sensors=sensors)
        except (FalaszError, StaticErrors) as err:
            errors = err.errors if isinstance(err, StaticErrors) else [err]
            for e in errors:
                assert e.path == "fuzz.falasz" and e.pos is not None, (src, e)
                assert e.category != "SyntaxError", (src, e)  # generator emits valid syntax
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"raw {type(exc).__name__}: {exc}\nsource:\n{src}")
