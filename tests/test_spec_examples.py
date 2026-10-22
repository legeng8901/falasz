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


# ------------------------------------------------- stage 2: parser vs. corpus

from falasz.errors import FalaszError, FalaszSyntaxError  # noqa: E402
from falasz.parser import parse  # noqa: E402

SYNTAX_INVALID = [p for p in INVALID if parse_err(p)[3] == "SyntaxError"]


def _parse_file(path):
    return parse(path.read_text(encoding="utf-8"), path.name)


@pytest.mark.parametrize("src", SYNTAX_INVALID, ids=example_id)
def test_parser_reports_expected_syntax_error(src):
    path, line, col, _ = parse_err(src)
    with pytest.raises(FalaszSyntaxError) as exc:
        _parse_file(path)
    assert (exc.value.path, exc.value.pos) == (path.name, (line, col)), exc.value.format()


@pytest.mark.parametrize(
    "src", [p for p in ALL_SOURCES if not any(p == parse_err(s)[0] for s in SYNTAX_INVALID)],
    ids=lambda p: str(p.relative_to(EXAMPLES)),
)
def test_other_examples_parse(src):
    _parse_file(src)


# ------------------------------------------- stage 3+: executing the corpus

import io  # noqa: E402

from falasz.runtime import StaticErrors, run_source  # noqa: E402

CURRENT_STAGE = 3
# Examples needing features of a later stage; everything else must pass now.
REQUIRES_STAGE = {
    "hello": 4, "scopes": 4, "arity": 4, "no_leak_to_outer": 4,
    "modules": 5, "local_shadow": 5, "not_exported": 5, "import_cycle": 5, "import_missing": 5,
}


def _skip_if_later_stage(src):
    stage = REQUIRES_STAGE.get(example_id(src), 0)
    if stage > CURRENT_STAGE:
        pytest.skip(f"requires stage {stage}")


def _run(src):
    out = io.StringIO()
    stdin = src.with_suffix(".in")
    inp = io.BytesIO(stdin.read_bytes()) if stdin.exists() else None
    run_source(src.read_text(encoding="utf-8"), src.name, out=out, inp=inp)
    return out.getvalue()


@pytest.mark.parametrize("src", VALID, ids=example_id)
def test_valid_example_output(src):
    _skip_if_later_stage(src)
    assert _run(src) == src.with_suffix(".out").read_text(encoding="utf-8")


@pytest.mark.parametrize("src", INVALID, ids=example_id)
def test_invalid_example_error(src):
    _skip_if_later_stage(src)
    path, line, col, category = parse_err(src)
    with pytest.raises((StaticErrors, FalaszError)) as exc:
        _run(src)
    err = exc.value.errors[0] if isinstance(exc.value, StaticErrors) else exc.value
    assert (err.path, err.pos, err.category) == (path.name, (line, col), category), err.format()


def test_stage_markers_refer_to_existing_examples():
    ids = {example_id(p) for p in VALID + INVALID}
    assert set(REQUIRES_STAGE) <= ids
