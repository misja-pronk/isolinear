# Isolinear

A fast, keyboard-driven terminal UI for managing Databricks secrets — browse scopes, secrets, and permissions across three panes without ever leaving your terminal.

![Isolinear browsing secrets](img/browse.svg)

Isolinear puts the full lifecycle of Databricks secret **scopes**, **secrets**, and **ACLs** behind a calm, three-pane browser. Drill from scopes into their secrets, reveal and copy values on demand, and review your effective access — all driven by the keyboard.

## Highlights

- **Three-pane browser** — scopes, secrets, and a rich detail pane (identity, your access, the full ACL list, and the revealed value).
- **Global search** — ++ctrl+f++ fuzzy-matches `scope/key` across the whole workspace and jumps straight to the secret.
- **Full CRUD with undo** — create, edit, and delete secrets and scopes, with confirmation on destructive actions and ++u++ to restore a deleted secret.
- **Permissions / ACLs** — grant, change, or remove READ / WRITE / MANAGE for users, groups, and service principals.
- **Lazy reveal, short-lived** — values are fetched only when you reveal or copy them, never bulk-loaded, and a revealed value hides itself after 30 seconds.
- **Copy as code** — ++shift+c++ copies a `dbutils.secrets.get(...)`, Spark-conf, or CLI reference for notebooks and job specs.
- **Authorization overview & stale-secret audit** — one-key views of your effective permission on every scope, and of every secret overdue for rotation.
- **Keyboard-first** — vim and arrow navigation, fuzzy filtering, sortable tables, and a command palette.
- **Read-only mode** — `isolinear --read-only` disables every mutation, safe for poking around production.
- **No pre-configuration** — connect by Databricks Asset Bundle, `~/.databrickscfg` profile, or workspace URL (OAuth).

## Quick start

=== "uvx"

    ```sh
    uvx isolinear
    ```

=== "uv tool"

    ```sh
    uv tool install isolinear
    isolinear
    ```

On launch, Isolinear opens a workspace picker that discovers connection targets automatically. Pick one, press ++enter++, and you're in.

## Next steps

- [Installation](installation.md) — install with uvx, uv tool, or pipx.
- [Connecting](connecting.md) — the workspace picker and its three sources.
- [Browsing & managing](browsing.md) — navigate, reveal, and manage secrets and permissions.
