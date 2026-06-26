# Vault — Databricks Secret Manager · User Stories

A keyboard-driven terminal app for managing Databricks secrets. Superfile-inspired
multi-pane layout with its own distinct "Vault" theme. Built with Python, Textual,
and the Databricks SDK.

> **Workspace** in this app = a connection profile in `~/.databrickscfg`.

---

## Epic 1 — Workspace connection & navigation
| ID | Story | Acceptance |
|----|-------|-----------|
| US-1 | See all configured workspaces (profiles) and pick one. | Profiles parsed from `~/.databrickscfg`; host shown; selectable on the login hub. |
| US-1a | Sign in with a workspace URL when no profile exists. | Paste host → OAuth U2M browser login (`auth_type=external-browser`); no token. |
| US-1b | Discover workspaces via the account (AWS/Azure/GCP). | Pick cloud + account ID → account OAuth → `workspaces.list()` → pick → `get_workspace_client`. |
| US-1c | Persist a login as a reusable profile. | Optional "save as" writes host+auth_type to `~/.databrickscfg`; instant next launch. |
| US-2 | Connection verified; shows authenticated identity. | `current_user.me()` resolved; username + status shown. |
| US-3 | Switch workspaces without restarting. | `w` opens the login hub; switching re-warms cache for new workspace. |

## Epic 2 — Browsing scopes & secrets
| ID | Story | Acceptance |
|----|-------|-----------|
| US-4 | Browse all scopes with backend type. | Scopes list shows `DATABRICKS` vs `AZURE_KEYVAULT`. |
| US-5 | Browse secret keys in a scope with timestamps. | Keys + last-updated shown for selected scope. |
| US-6 | Detail panel for selected secret/scope. | Right pane shows metadata + ACLs. |

## Epic 3 — Secret operations (CRUD)
| ID | Story | Acceptance |
|----|-------|-----------|
| US-7 | Create a secret (key + value) in a scope. | `put_secret`; cache + list update. |
| US-8 | Update an existing secret's value. | `put_secret` on existing key; timestamp refreshes. |
| US-9 | Delete a secret with confirmation. | Confirm modal; `delete_secret`; row removed. |
| US-10 | Reveal & copy a secret value. | `get_secret`; reveal toggle; copy to clipboard. |
| US-11 | Create & delete scopes. | `create_scope` / `delete_scope` with confirm. |
| US-11a | Update a scope's permissions (ACLs). | `p` opens a permissions editor; `put_acl` / `delete_acl` (a scope is otherwise immutable). |

## Epic 4 — Authorization overview
| ID | Story | Acceptance |
|----|-------|-----------|
| US-12 | See & edit ACLs (principal + permission) per scope. | `list_acls` in detail pane; full add/change/remove via the `p` editor. |
| US-13 | Authorization status overview. | My identity + my effective permission per scope; write-capable flagged. |

## Epic 5 — Performance & UX (caching / pre-call)
| ID | Story | Acceptance |
|----|-------|-----------|
| US-14 | Pre-load scopes, secret metadata, ACLs on startup. | Background worker warms cache; progress shown. |
| US-15 | Refresh cache on demand. | `r` refreshes scope; `R` refreshes workspace. |
| US-16 | Lazy + cached secret values. | Values fetched only on reveal; cached thereafter. |

## Epic 6 — Look & feel
| ID | Story | Acceptance |
|----|-------|-----------|
| US-17 | Distinct "Vault" theme. | Deep-navy/teal/amber palette, lock motifs, multi-pane. |
| US-18 | Keyboard-driven with footer + help overlay. | Footer bindings; `?` help screen. |

---

## Out of scope (v1 / future)
- Account-level workspace enumeration (requires account auth).
- Secret value history / versioning (not exposed by the API).
- Bulk import/export of secrets.
- Renaming a scope (immutable in the Databricks API — delete + recreate).
