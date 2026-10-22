"""Consistency checks for the spec example corpus (tests/spec_examples).

Layout (docs/spec.md, section 13):
  valid/X.falasz + X.out [+ X.in]       single-file program
  valid/X/main.falasz + main.out         multi-file program
  invalid/X.falasz + X.err               single-file program
  invalid/X/main.falasz + main.err       multi-file program
First line of .err: "<file>:<line>:<col>: <Category>", <file> relative to the example dir.
"""

import re
from pathlib import Path

import pytest

import falasz

EXAMPLES = Path(__file__).parent / "spec_examples"
CATEGORIES = {
    "SyntaxError", "NameError", "TypeError", "ValueError", "ArityError",
    "ZeroDivisionError", "ArithmeticError", "IndexError", "KeyError",
    "ImportError", "FileError", "SensorError", "RecursionLimitError", "LimitError",
}
ERR_LINE = re.compile(r"^([\w.-]+\.falasz):(\d+):(\d+): (\w+)$")


def entry_points(kind):
    root = EXAMPLES / kind
    return sorted(
        [p for p in root.glob("*.falasz")]
        + [d / "main.falasz" for d in root.iterdir() if d.is_dir()]
    )


def example_id(path):
    return path.stem if path.name != "main.falasz" else path.parent.name


VALID = entry_points("valid")
INVALID = entry_points("invalid")
ALL_SOURCES = sorted(EXAMPLES.rglob("*.falasz"))


def parse_err(src):
    err = src.with_suffix(".err").read_text(encoding="utf-8")
    m = ERR_LINE.match(err.splitlines()[0])
    assert m, f"malformed .err: {err!r}"
    return src.parent / m[1], int(m[2]), int(m[3]), m[4]


def test_version():
    assert falasz.__version__ == "0.1.0a0"


def test_corpus_not_empty():
    assert VALID and INVALID


@pytest.mark.parametrize("src", VALID, ids=example_id)
def test_valid_example_has_expected_output(src):
    out = src.with_suffix(".out")
    assert out.is_file()
    assert out.read_text(encoding="utf-8").endswith("\n")


@pytest.mark.parametrize("src", INVALID, ids=example_id)
def test_invalid_example_has_wellformed_error(src):
    path, line, col, category = parse_err(src)
    assert category in CATEGORIES
    assert path.is_file(), f"{path} referenced by .err does not exist"
    lines = path.read_text(encoding="utf-8").split("\n")
    # Location must point inside the file (EOF position = line after last newline, col 1).
    assert 1 <= line <= len(lines)
    assert 1 <= col <= len(lines[line - 1]) + 1


@pytest.mark.parametrize("src", ALL_SOURCES, ids=lambda p: str(p.relative_to(EXAMPLES)))
def test_sources_are_utf8_without_crlf(src):
    data = src.read_bytes()
    data.decode("utf-8")
    assert b"\r" not in data


@pytest.mark.parametrize(
    "src", [p for p in ALL_SOURCES if p.name != "main.falasz" and p.parent.name not in ("valid", "invalid")],
    ids=lambda p: str(p.relative_to(EXAMPLES)),
)
def test_module_files_have_no_expectation_files(src):
    # Only main.falasz is an entry point inside a multi-file example.
    assert not src.with_suffix(".out").exists() and not src.with_suffix(".err").exists()
