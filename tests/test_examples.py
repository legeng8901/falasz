"""Programs in examples/ must run and produce the recorded output (<name>.out, stdin <name>.in)."""

import io
from pathlib import Path

import pytest

from falasz.runtime import run_source

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.falasz"))


def test_examples_exist():
    assert EXAMPLES


@pytest.mark.parametrize("src", EXAMPLES, ids=lambda p: p.stem)
def test_example(src):
    stdin = src.with_suffix(".in")
    out = io.StringIO()
    run_source(src.read_text(encoding="utf-8"), src.name, out=out,
               inp=io.BytesIO(stdin.read_bytes()) if stdin.exists() else None)
    assert out.getvalue() == src.with_suffix(".out").read_text(encoding="utf-8")
