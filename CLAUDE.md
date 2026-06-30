# CLAUDE.md

Guidance for Claude / agents working in this repo. **Isolinear** is a
keyboard-driven Textual TUI for managing Databricks secrets.

## Toolchain — use these, nothing else

This project is **all-[Astral](https://astral.sh)**, version-managed by
**[mise](https://mise.jdx.dev)**. Reach for exactly these four tools:

| Tool | Role | How it's provided |
|------|------|-------------------|
| **mise** | Provisions the toolchain (Python 3.14, uv) | `mise.toml` → `mise install` |
| **uv** | Env, deps, and command runner (`.venv`) | installed by mise |
| **ruff** | Lint **and** format | `uv run ruff` |
| **ty** | Type checking | `uv run ty` |

**Rules:**

- **Never** use system `python`/`python3`, bare `pip`, `virtualenv`, `poetry`,
  `pipenv`, `conda`, `black`, `flake8`, `isort`, `mypy`, or hand-rolled `.venv`s.
  uv replaces pip/virtualenv; ruff replaces black/flake8/isort; ty replaces mypy.
- **Always** invoke project tools through `uv run …` (uv comes from mise, so it
  resolves the right Python and the project `.venv` automatically).
- Need a one-off dependency for a script (e.g. an image lib for mockups)?
  Use `uv run --with <pkg> python script.py` — **do not** install it into the
  project or create a separate venv.
- Add a real dependency with `uv add <pkg>` (runtime) or `uv add --dev <pkg>`
  (dev tooling). This edits `pyproject.toml` + `uv.lock` — never edit `.venv`
  by hand.

> If `uv` isn't on `PATH` in a non-interactive shell, it's because mise hasn't
> activated. Use `mise exec -- uv …` (or `eval "$(mise activate bash)"` first).

## Commands

```sh
mise install            # one-time: install Python + uv per mise.toml
uv sync                 # create/refresh .venv from pyproject + uv.lock (incl. dev group)

uv run isolinear        # run the app (alias: uv run iso)
uv run pytest           # tests (core units + UI via Textual Pilot)
uv run ruff check .     # lint
uv run ruff format .    # format
uv run ty check         # type check
```

**Before committing**, all of these must pass: `uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest`.

## Architecture

Hexagonal / DDD — dependencies point **inward**, all I/O sits behind domain
ports, so the domain is unit-testable with no network. Respect the layering:

```
src/isolinear/
  domain/          model, rules + ports (SecretStore, WorkspaceConnector, ProfileStore)
  application/     use-cases (WorkspaceService, OnboardingService) + read model
  infrastructure/  adapters — the ONLY place the Databricks SDK is imported
  interface/       Textual presentation — no business logic, no infra imports
  app.py           composition root (wires it all together)
```

- The `interface/` layer never touches the SDK or infra directly — it talks to
  `application/` services. The `domain/` layer imports nothing outward.
- UI theming lives in `interface/theme.py` (Textual `Theme`s) and
  `styles.tcss` (Textual CSS).

## Conventions

- Python ≥ 3.11 syntax (`from __future__ import annotations` is used throughout).
- ruff: line length **90**, rules `E,F,I,UP,B,SIM` (see `pyproject.toml`).
- ty must report no errors.
- Keep blocking I/O off the UI thread — services run in worker threads via
  `asyncio.to_thread` (see `interface/screens/main.py`).
