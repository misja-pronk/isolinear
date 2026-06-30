# Isolinear

A fast, keyboard-driven terminal UI for managing Databricks secrets — browse scopes, secrets, and permissions across three panes without ever leaving your terminal.

![Isolinear browsing secrets](img/browse.png)

Isolinear puts the full lifecycle of Databricks secret **scopes**, **secrets**, and **ACLs** behind a calm, three-pane browser. Drill from scopes into their secrets, reveal and copy values on demand, and review your effective access — all driven by the keyboard.

## Highlights

- **Three-pane browser** — scopes, secrets, and a rich detail pane (identity, your access, the full ACL list, and the revealed value).
- **Full CRUD** — create, edit, and delete secrets and scopes, with confirmation on destructive actions.
- **Permissions / ACLs** — grant, change, or remove READ / WRITE / MANAGE for users, groups, and service principals.
- **Lazy reveal** — secret values are fetched only when you reveal or copy them, never bulk-loaded.
- **Authorization overview** — a one-key "what can I touch" view of your effective permission on every scope.
- **Keyboard-first** — vim and arrow navigation, fuzzy filtering, sortable tables, and a command palette.
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
