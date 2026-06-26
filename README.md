# Keystone ⏢ — Databricks Secret Manager

A keyboard-driven terminal app for browsing and managing Databricks secrets,
scopes, and ACLs. Superfile-inspired multi-pane layout with its own distinct
**Keystone** theme. Built with [Textual](https://textual.textualize.io) and the
[Databricks SDK](https://github.com/databricks/databricks-sdk-py).

## Features
- Browse workspaces (profiles), scopes, and secrets in a fast multi-pane UI
- Create / update / delete secrets and scopes
- Reveal & copy secret values to the clipboard
- Authorization overview (identity + per-scope ACLs)
- Pre-loads & caches everything on startup for an instant experience

## Requirements
Tooling is pinned via [`mise`](https://mise.jdx.dev) + [`uv`](https://docs.astral.sh/uv/).

```sh
mise install      # installs python 3.12 + uv
uv sync           # creates .venv and installs deps
```

## Logging in
You do **not** need to pre-configure anything. On first launch (no usable
profile) Keystone opens an onboarding hub with two doors:

1. **Workspace URL** — paste a workspace URL and sign in through your browser
   (OAuth U2M / SSO). No token required.
2. **Discover via account** — pick your cloud (AWS / Azure / GCP), paste your
   Account ID, sign in once, and Keystone lists **every workspace in the account**
   for you to choose from.

Either way you can tick *save as profile name* and Keystone writes a reusable
profile to `~/.databrickscfg` (host + `auth_type = external-browser`, no secret
stored — same as `databricks auth login`), so next launch connects instantly.

### Already have profiles?
Keystone also reads existing connection **profiles** from `~/.databrickscfg` and
shows them on the hub for one-keypress reconnect:

```ini
[prod]
host  = https://my-workspace.cloud.databricks.com
token = dapi...

[staging]
host      = https://staging.cloud.databricks.com
auth_type = external-browser
```

Press `w` anytime to switch workspace or add a new connection.

## Run

```sh
uv run keystone
```

## Architecture
Hexagonal / DDD. Dependencies point inward; **all I/O is behind domain ports**,
and the UI never touches infrastructure (`interface → application → domain ←
infrastructure`):

```
keystone/
  domain/                # the model, rules + ports — pure (no Textual/SDK/asyncio)
    models.py            #   Scope / Secret / Acl / Identity / Workspace …
    permissions.py       #   perm ranking + authorization_summary (US-13)
    host.py              #   normalize_host (a small rule)
    secret_store.py      #   SecretStore  — repository port
    ports.py             #   WorkspaceConnector / AccountSession / ProfileStore
    errors.py            #   StoreError / AuthError
  application/           # use-cases / orchestration (depends on domain only)
    workspace.py         #   WorkspaceService — secret-management use-cases
    onboarding.py        #   OnboardingService — login/discovery use-cases
    read_model.py        #   WorkspaceCache — in-memory projection the UI renders
  infrastructure/        # adapters implementing the ports (only SDK importers)
    databricks.py        #   DatabricksSecretStore  (SecretStore)
    connector.py         #   DatabricksConnector    (WorkspaceConnector)
    profiles.py          #   DatabricksCfgProfileStore (ProfileStore)
    config.py            #   config-file location
  interface/             # Textual presentation — NO business logic, NO infra
    theme.py  widgets.py  modals.py  screens/
  app.py                 # composition root: build adapters → wire → run
```

- **Ports & adapters:** the domain defines `SecretStore`, `WorkspaceConnector`,
  and `ProfileStore` as `Protocol`s; infrastructure implements them. Nothing
  outside `infrastructure/` imports the Databricks SDK.
- **The UI depends only on `application` + `domain`.** It talks to
  `WorkspaceService` / `OnboardingService`; `app.py` injects the concrete
  adapters. Tests inject in-memory fakes.
- **The domain stays pure:** authorization rules live in `domain/permissions.py`,
  not on the cache; the cache is a plain read-model projection.

## Development

The toolkit is all-Astral: **[uv](https://docs.astral.sh/uv/)** (env / deps / run),
**[ruff](https://docs.astral.sh/ruff/)** (lint + format), and
**[ty](https://docs.astral.sh/ty/)** (type check). Python is pinned to the latest
(3.14) via `mise`. CI runs them all on every push (`.github/workflows/ci.yml`).

```sh
uv sync                  # install incl. dev deps
uv run pytest            # test suite (core units + UI via Textual Pilot)
uv run ruff check .      # lint
uv run ruff format .     # format
uv run ty check          # type check
uv run textual run --dev keystone.app:KeystoneApp   # run with Textual devtools
```

The `core/` layer is covered by fast unit tests; the `ui/` layer is driven
through Textual's `Pilot` harness with a fake gateway (no network).

## Keys
Everything is keyboard driven. Press `?` for the in-app cheat-sheet or `ctrl+p`
for the fuzzy command palette.

| Key | Action |
|-----|--------|
| `↑↓` / `j` `k` | Move within a pane |
| `←→` / `h` `l` | Move between panes |
| `tab` · `enter` | Next pane · drill scope → secrets |
| `g` / `G` | Jump to top / bottom |
| `n` / `N` | New secret / new scope |
| `e` | Edit secret value |
| `d` | Delete secret/scope (with confirm) |
| `p` | Manage scope permissions (ACLs) |
| `space` · `c` | Reveal value · copy value |
| `r` / `R` | Refresh scope / workspace |
| `a` | Authorization overview |
| `w` · `ctrl+p` | Switch workspace · command palette |
| `?` · `q` | Help · quit |
