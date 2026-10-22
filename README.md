# Falasz

Falasz is a general-purpose programming language with English keywords.
Version 0.1 is an alpha-stage tree-walking interpreter written in Python 3.12+.

**Status:** under development. Stage 2 is done: the lexer and parser are written and tested, but nothing can be executed yet.
The language specification is in [docs/spec.md](docs/spec.md).

## Development

    python3 -m venv .venv
    .venv/bin/pip install -e '.[dev]'
    .venv/bin/pytest
