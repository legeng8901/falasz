"""Code in the user documentation must be valid Falasz and print what the text says.

Every ```falasz block in README.md and docs/getting-started.md must pass
`check`. Blocks that do not read standard input are also run; when a ```text
block follows directly, it is the expected output.
"""

import io
import re
import textwrap
from pathlib import Path

import pytest

from falasz.runtime import check_source, run_source

ROOT = Path(__file__).parent.parent
DOCS = ["README.md", "docs/getting-started.md"]

FENCE = re.compile(r"^( *)```(\w*)\n(.*?)^\1```\n", re.MULTILINE | re.DOTALL)


def blocks(doc):
    """(line, code, expected output or None) for each falasz block of `doc`."""
    text = (ROOT / doc).read_text(encoding="utf-8")
    fences = list(FENCE.finditer(text))
    result = []
    for i, m in enumerate(fences):
        if m.group(2) != "falasz":
            continue
        expected = None
        if i + 1 < len(fences):
            following = fences[i + 1]
            if following.group(2) == "text" and text[m.end():following.start()].strip() == "":
                expected = textwrap.dedent(following.group(3))
        line = text.count("\n", 0, m.start()) + 1
        result.append((line, textwrap.dedent(m.group(3)), expected))
    return result


CASES = [(doc, line, code, expected) for doc in DOCS for line, code, expected in blocks(doc)]


def test_documents_have_examples():
    assert {doc for doc, *_ in CASES} == set(DOCS)
    assert sum(expected is not None for *_, expected in CASES) >= 6


@pytest.mark.parametrize("doc, line, code, expected", CASES, ids=[f"{d}:{l}" for d, l, _, _ in CASES])
def test_documented_code(doc, line, code, expected, tmp_path):
    path = tmp_path / "doc.falasz"
    path.write_text(code, encoding="utf-8")
    result = check_source(None, str(path))
    assert result.errors == [], f"{doc}:{line}: {result.errors[0].format()}"
    if "INPUT(" in code:
        return  # needs a person at the keyboard; checked only
    out = io.StringIO()
    run_source(None, str(path), out=out, inp=io.BytesIO(b""))
    if expected is not None:
        assert out.getvalue() == expected
