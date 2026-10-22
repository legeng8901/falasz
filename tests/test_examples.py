"""Programs in examples/ must run and produce the recorded output.

examples/<name>.falasz or examples/<name>/main.falasz (multi-file), with
<name>.out = expected stdout, <name>.in = stdin, <name>.err = expected error with
traceback (only for examples that intentionally fail). Each example runs on a
copy in a temporary directory, so examples that write files leave no trace.
"""

import contextlib
import io
import shutil
from pathlib import Path

import pytest

from falasz.errors import FalaszError
from falasz.runtime import run_file

ROOT = Path(__file__).parent.parent / "examples"
EXAMPLES = sorted(
    list(ROOT.glob("*.falasz")) + [d / "main.falasz" for d in ROOT.iterdir() if d.is_dir()]
)


def example_id(path):
    return path.parent.name if path.name == "main.falasz" else path.stem


def test_examples_exist():
    assert EXAMPLES


@pytest.mark.parametrize("src", EXAMPLES, ids=example_id)
def test_example(src, tmp_path):
    if src.name == "main.falasz":
        workdir = tmp_path / src.parent.name
        shutil.copytree(src.parent, workdir)
    else:
        workdir = tmp_path
        shutil.copy(src, workdir)
    stdin = src.with_suffix(".in")
    expected_err = src.with_suffix(".err")
    out = io.StringIO()
    try:
        with contextlib.chdir(workdir):
            run_file(src.name, out=out, inp=io.BytesIO(stdin.read_bytes()) if stdin.exists() else None)
    except FalaszError as err:
        assert expected_err.exists(), err.format_with_trace()
        assert err.format_with_trace() + "\n" == expected_err.read_text(encoding="utf-8")
    else:
        assert not expected_err.exists(), "expected the example to fail"
    assert out.getvalue() == src.with_suffix(".out").read_text(encoding="utf-8")
