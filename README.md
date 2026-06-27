# Isolinear ▦

**A keyboard-driven terminal UI for managing Databricks secrets.**
Browse workspaces, scopes, secrets and ACLs; create / edit / delete; reveal &
copy values — all from a fast, LCARS-flavoured TUI.

[![ci](https://github.com/misja-pronk/isolinear/actions/workflows/ci.yml/badge.svg)](https://github.com/misja-pronk/isolinear/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/isolinear.svg)](https://pypi.org/project/isolinear/)
[![Python](https://img.shields.io/pypi/pyversions/isolinear.svg)](https://pypi.org/project/isolinear/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

![Isolinear browsing secrets](docs/img/browse.png)

## Install

Run it with [uv](https://docs.astral.sh/uv/) — no clone, no virtualenv:

```sh
uvx isolinear              # run once, ephemerally
uv tool install isolinear  # install the `isolinear` (and `iso`) commands on PATH
```

Or with pipx: `pipx run isolinear` / `pipx install isolinear`.

> Requires Python ≥ 3.11. Built with [Textual](https://textual.textualize.io)
> and the [Databricks SDK](https://github.com/databricks/databricks-sdk-py).

## Quickstart

```sh
isolinear        # or: iso
```

You **don't** need to pre-configure anything. On first launch Isolinear opens an
onboarding hub with two doors:

1. **Workspace URL** — paste a workspace URL and sign in through your browser
   (OAuth U2M / SSO). No token required.
2. **Discover via account** — pick your cloud (AWS / Azure / GCP), paste your
   Account ID, sign in once, and Isolinear lists **every workspace in the
   account** for you to choose from.

Tick *save as profile* and it writes a reusable entry to `~/.databrickscfg`
(host + `auth_type = external-browser`, **no secret stored** — same as
`databricks auth login`), so next launch connects instantly. Existing
`~/.databrickscfg` profiles show up automatically.

<table>
  <tr>
    <td><img src="docs/img/login.png" alt="Login hub"></td>
    <td><img src="docs/img/auth.png" alt="Authorization overview"></td>
  </tr>
  <tr>
    <td align="center"><sub>Onboarding hub</sub></td>
    <td align="center"><sub>Authorization overview</sub></td>
  </tr>
</table>

## Features

- **Three-pane browser** — scopes (with secret counts + your access), secrets
  (with relative age), and a detail pane.
- **Reveal & copy** secret values; values are fetched lazily on reveal and never
  bulk-pulled into memory.
- **Full CRUD** — create / edit / delete secrets, create / delete scopes,
  manage scope **permissions (ACLs)**.
- **Authorization overview** — your effective permission on every scope.
- **Fuzzy filter** (`/`), **command palette** (`ctrl+p`), vim + arrow navigation.
- **Multiple workspaces** — switch profiles, or add new connections on the fly.
- **Pre-loads & caches** everything on startup for an instant experience.
- Three switchable themes (violet, amber Okudagram, phosphor green).

## Keys

Everything is keyboard driven. Press `?` for the in-app cheat-sheet or `ctrl+p`
for the fuzzy command palette.

| Key | Action |
|-----|--------|
| `↑↓` / `j` `k` | Move within a pane |
| `←→` / `h` `l` · `tab` | Move between panes |
| `g` / `G` | Jump to top / bottom |
| `/` | Filter the focused pane |
| `n` / `N` | New secret / new scope |
| `e` · `d` | Edit secret · delete (with confirm) |
| `p` | Manage scope permissions (ACLs) |
| `space` · `c` | Reveal / hide value · copy value |
| `r` / `R` | Refresh scope / workspace |
| `a` | Authorization overview |
| `w` · `ctrl+p` | Switch workspace · command palette |
| `?` · `q` | Help · quit |

## Security

Isolinear talks to Databricks through the official SDK's unified auth. It does
**not** store secret *values* — they're read on demand and kept only in memory.
Saved profiles contain a host + `auth_type`, never a token. See
[SECURITY.md](SECURITY.md) for details and how to report a vulnerability.

## How it's built

Hexagonal / DDD layers; dependencies point inward and **all I/O is behind domain
ports**, so the UI never touches the SDK and the whole domain is unit-testable
without a network:

```
isolinear/
  domain/          model, rules + ports (SecretStore, WorkspaceConnector, ProfileStore)
  application/     use-cases (WorkspaceService, OnboardingService) + read model
  infrastructure/  adapters — the only Databricks-SDK importers
  interface/       Textual presentation (no business logic, no infra)
  app.py           composition root
```

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The toolkit is
all-[Astral](https://astral.sh): **uv** (env/deps/run), **ruff** (lint+format),
**ty** (types).

```sh
uv sync
uv run pytest        # tests (core units + UI via Textual Pilot)
uv run ruff check .  # lint
uv run ty check      # types
uv run isolinear     # run it
```

## License

[MIT](LICENSE) © Misja Pronk
