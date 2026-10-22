"""Programs in examples/ must run and produce the recorded output.

<name>.out = expected stdout, <name>.in = stdin, <name>.err = expected error with traceback
(only for examples that intentionally fail).
"""

import io
from pathlib import Path

import pytest

from falasz.errors import FalaszError
from falasz.runtime import run_source

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.falasz"))


def test_examples_exist():
    assert EXAMPLES


@pytest.mark.parametrize("src", EXAMPLES, ids=lambda p: p.stem)
def test_example(src):
    stdin = src.with_suffix(".in")
    expected_err = src.with_suffix(".err")
    out = io.StringIO()
    try:
        run_source(src.read_text(encoding="utf-8"), src.name, out=out,
                   inp=io.BytesIO(stdin.read_bytes()) if stdin.exists() else None)
    except FalaszError as err:
        assert expected_err.exists(), err.format_with_trace()
        assert err.format_with_trace() + "\n" == expected_err.read_text(encoding="utf-8")
    else:
        assert not expected_err.exists(), "expected the example to fail"
    assert out.getvalue() == src.with_suffix(".out").read_text(encoding="utf-8")
