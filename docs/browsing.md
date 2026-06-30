# Browsing & managing

The browser is built from three panes. The header shows a breadcrumb — `scope: X / secret: Y` — so you always know where you are.

![The three-pane browser with a secret revealed](img/browse.svg)

| Pane | Shows |
|------|-------|
| **Left — scopes** | Each scope's name and secret count. |
| **Middle — secrets** | The keys in the selected scope, with last-updated and a relative age. |
| **Right — detail** | Identity, your access, the scope's full ACL list, and the revealed value card. |

On startup, Isolinear pre-loads and caches scopes, secrets, and ACLs for an instant feel.

## Navigating

- Move within a pane with ++up++ ++down++ or ++j++ ++k++.
- Move between panes with ++left++ ++right++ / ++h++ ++l++, or ++tab++.
- Jump to the top or bottom with ++g++ / ++shift+g++.
- Selecting a scope drills into its secrets.

See the [Keyboard](keyboard.md) page for the complete key table.

## Sorting and filtering

Both the scopes and secrets tables are **sortable**. Click a column header or press ++s++ to cycle the sort column and direction; a ↑ / ↓ marks the active column.

Press ++slash++ to fuzzy-filter the focused pane.

## Revealing and copying values

Reveal a value with ++space++ or copy it with ++c++. Revealing shows the value in an amber "live" card in the detail pane.

!!! warning "Values are fetched lazily"
    Secret values are read on demand — only when you reveal or copy them — and are **never bulk-loaded**. Nothing about a value leaves Databricks until you ask for it. Copying places the value on your system clipboard; clear it if you share your machine.

## Creating, editing, and deleting

- **New secret** — ++n++
- **Edit secret** — ++e++
- **Delete secret** — ++d++
- **New scope** — ++shift+n++
- **Delete scope** — ++d++ on a selected scope

Destructive actions show a confirmation dialog before anything is removed.

![Delete confirmation dialog](img/confirm.svg)

## Managing permissions (ACLs)

Press ++p++ to manage a scope's permissions. From the modal you can grant, change, or remove **READ**, **WRITE**, or **MANAGE** for a principal — a user, group, or service principal.

![Scope permissions modal](img/perms.svg)

!!! note "Privilege levels are colour-coded"
    Permission levels are coloured by privilege: **READ** muted, **WRITE** cyan, **MANAGE** amber and bold — so the strongest grants stand out at a glance.

## Authorization overview

Press ++a++ for a modal listing every scope with your **effective** permission and the number of principals, sorted by privilege. It's a fast "what can I touch" view across the whole workspace.

![Authorization overview modal](img/auth.svg)

## Refreshing

- Refresh the selected scope with ++r++.
- Refresh the whole workspace with ++shift+r++.
