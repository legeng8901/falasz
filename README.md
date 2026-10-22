# Falasz

Falasz is a general-purpose programming language with English keywords.
Version 0.1 is an alpha-stage tree-walking interpreter written in Python 3.12+.

**Status:** under development (stage 6 of 8). All language features of v0.1 run through the Python API (`falasz.runtime.run_file`); the `falasz` command comes in stage 7. See [docs/limitations.md](docs/limitations.md) for what is missing.
The language specification is in [docs/spec.md](docs/spec.md); the sensors API is in [docs/sensors.md](docs/sensors.md).

## Development

    python3 -m venv .venv
    .venv/bin/pip install -e '.[dev]'
    .venv/bin/pytest
