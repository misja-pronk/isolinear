# Isolinear — Databricks Secret Manager · User Stories

A keyboard-driven terminal app for managing Databricks secrets. A superfile-inspired
three-pane layout with a calm, distinctly "Isolinear" look. Built with Python, Textual,
and the Databricks SDK.

> **Workspace** in this app = a connection target Isolinear can reach: a Databricks
> Asset Bundle workspace, a `~/.databrickscfg` profile, or a URL you sign in to.

---

## Epic 1 — Workspace connection & navigation
| ID | Story | Acceptance |
|----|-------|-----------|
| US-1 | See connection targets from every source and pick one. | The picker lists asset-bundle, `~/.databrickscfg`, and URL targets; each row labelled with its **Source**; selectable. |
| US-1a | An asset-bundle workspace is offered as the default. | A `databricks.yml` in the working dir → its target (`default: true`, else the sole target, else the top-level `workspace.host`) is pre-selected; `${...}` variables fall back to the top-level host. |
| US-1b | Sign in with a workspace URL. | *Add by URL* → OAuth U2M browser login (`auth_type=external-browser`); no token stored. |
| US-1c | Persist a login as a reusable profile. | Optional "save as" writes host + auth_type to `~/.databrickscfg`; instant next launch. |
| US-2 | Connection verified; shows authenticated identity. | `current_user.me()` resolved; username + status shown. |
| US-3 | Switch workspaces without restarting. | `w` reopens the picker; switching re-warms the cache for the new workspace. |

## Epic 2 — Browsing scopes & secrets
| ID | Story | Acceptance |
|----|-------|-----------|
| US-4 | Browse all scopes with their secret counts. | Scopes table shows name + secret count; backend type (`DATABRICKS` / `AZURE_KEYVAULT`) shown in the detail pane. |
| US-5 | Browse secret keys in a scope with timestamps. | Keys + last-updated + relative age shown for the selected scope. |
| US-6 | Detail pane for the selection. | Right pane shows identity, your access, the scope's ACLs, and (on reveal) the value. |
| US-6a | Sort either table. | Click a column header or press `s` to cycle column + direction; the active column is marked ↑/↓; the selection is preserved across a sort. |
| US-6b | Fuzzy-filter the focused pane. | `/` filters scopes or secrets by subsequence match; `esc` clears. |

## Epic 3 — Secret operations (CRUD)
| ID | Story | Acceptance |
|----|-------|-----------|
| US-7 | Create a secret (key + value) in a scope. | `put_secret`; cache + list update. |
| US-8 | Update an existing secret's value. | `put_secret` on an existing key; timestamp refreshes. |
| US-9 | Delete a secret with confirmation. | Confirm modal; `delete_secret`; row removed. |
| US-10 | Reveal & copy a secret value. | `get_secret`; reveal toggle (`space`); copy to clipboard (`c`). |
| US-11 | Create & delete scopes. | `create_scope` / `delete_scope` with confirm. |
| US-11a | Update a scope's permissions (ACLs). | `p` opens the permissions editor; `put_acl` / `delete_acl` (a scope is otherwise immutable). |

## Epic 4 — Authorization overview
| ID | Story | Acceptance |
|----|-------|-----------|
| US-12 | See & edit ACLs (principal + permission) per scope. | `list_acls` in the detail pane + the `p` editor (add / change / remove READ / WRITE / MANAGE). |
| US-13 | Authorization status overview. | `a` lists every scope with my effective permission + principal count, sorted by privilege; levels colour-coded. |

## Epic 5 — Performance & UX (caching / pre-call)
| ID | Story | Acceptance |
|----|-------|-----------|
| US-14 | Pre-load scopes, secret metadata, ACLs on startup. | Background worker warms the cache; progress shown. |
| US-15 | Refresh cache on demand. | `r` refreshes the scope; `R` refreshes the workspace. |
| US-16 | Lazy + cached secret values. | Values fetched only on reveal; cached thereafter; never bulk-pulled. |
| US-16a | Command palette + quick actions. | `ctrl+p` opens a fuzzy command palette for every action. |

## Epic 6 — Look & feel
| ID | Story | Acceptance |
|----|-------|-----------|
| US-17 | Calm, distinct "Isolinear" look. | Graphite base; each pane carries a section accent (scopes violet, secrets cyan, detail amber) on its border, title, and selection. |
| US-17a | Switchable themes. | Graphite (default) plus violet / amber / phosphor skins, switched from the command palette. |
| US-18 | Keyboard-driven with footer + help overlay. | Context-aware footer bindings; `?` help screen. |

---

## Out of scope (by design / future)
- **Account-level workspace enumeration** (pick a cloud + Account ID). Removed by
  design — it added an account-auth round-trip for little gain; connect by an asset
  bundle, a profile, or a URL instead.
- Secret value history / versioning (not exposed by the API).
- Bulk import / export of secrets.
- Renaming a scope (immutable in the Databricks API — delete + recreate).
