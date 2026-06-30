# Contributing

Isolinear uses an all-[Astral](https://astral.sh) toolchain, version-managed by [mise](https://mise.jdx.dev). Reach for exactly these four tools.

| Tool | Role | Provided by |
|------|------|-------------|
| **mise** | Provisions Python 3.14 + uv | `mise install` |
| **uv** | Env, deps, and command runner (`.venv`) | mise |
| **ruff** | Lint **and** format | `uv run ruff` |
| **ty** | Type checking | `uv run ty` |

!!! warning "Do not use other tools"
    Never use system `pip` / `python` / `virtualenv`, or `poetry`, `pipenv`, `conda`, `black`, `flake8`, `isort`, or `mypy`. uv replaces pip/virtualenv; ruff replaces black/flake8/isort; ty replaces mypy.

## Commands

```sh
mise install            # one-time: install Python + uv per mise.toml
uv sync                 # create/refresh .venv from pyproject + uv.lock

uv run isolinear        # run the app (alias: uv run iso)
uv run pytest           # run the tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run ty check         # type check
```

## Before committing

All of these must pass:

```sh
uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest
```

## Previewing the docs

```sh
uv run --group docs mkdocs serve
```

## Conventions

- Python ≥ 3.11 syntax (`from __future__ import annotations` throughout).
- ruff: line length **90**, rules `E`, `F`, `I`, `UP`, `B`, `SIM`.
- ty must report no errors.

## Releasing

Releases are **version-driven** — `version` in `pyproject.toml` is the single
source of truth, and merging a bump to `main` ships it.

```sh
uv version --bump patch   # or minor / major — edits pyproject.toml + uv.lock
```

Move the `## [Unreleased]` notes in `CHANGELOG.md` under a new `## [x.y.z]`
heading, open a PR, and merge. The `release` workflow then publishes to PyPI
(Trusted Publishing) and creates the matching `vX.Y.Z` tag + GitHub release.
A merge that doesn't change the version does nothing.

For the full process and the one-time PyPI setup, see
[CONTRIBUTING.md](https://github.com/misja-pronk/isolinear/blob/main/CONTRIBUTING.md).

For pull-request mechanics, see [CONTRIBUTING.md](https://github.com/misja-pronk/isolinear/blob/main/CONTRIBUTING.md) in the repository.
