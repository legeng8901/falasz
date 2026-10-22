# Falasz

Falasz is a general-purpose programming language with English keywords.
Version 0.1 is an alpha-stage tree-walking interpreter written in Python 3.12+.

**Status:** under development (stage 3 of 8). Programs without functions and modules run through the Python API; there is no `falasz` command yet. See [docs/limitations.md](docs/limitations.md) for what is missing.
The language specification is in [docs/spec.md](docs/spec.md).

## Development

    python3 -m venv .venv
    .venv/bin/pip install -e '.[dev]'
    .venv/bin/pytest
