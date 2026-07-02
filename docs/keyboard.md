# Keyboard

Everything in Isolinear is keyboard-driven. Press ++question++ at any time for the in-app cheat-sheet, or ++ctrl+p++ to open the command palette.

| Keys | Action |
|------|--------|
| ++up++ ++down++ / ++j++ ++k++ | Move within a pane |
| ++left++ ++right++ / ++h++ ++l++ · ++tab++ | Move between panes |
| ++g++ / ++shift+g++ | Jump to top / bottom |
| ++enter++ | Scopes: open · Secrets: reveal / hide |
| ++slash++ | Filter the focused pane (++up++ ++down++ move while typing, ++esc++ clears) |
| ++ctrl+f++ | Search every scope |
| ++s++ / ++shift+s++ | Sort: next column / reverse direction |
| ++n++ / ++shift+n++ | New secret / new scope |
| ++e++ · ++d++ | Edit secret · delete (with confirm) |
| ++u++ | Undo the last secret delete |
| ++p++ | Manage scope permissions (ACLs) |
| ++space++ | Reveal / hide value (auto-hides after 30 s) |
| ++c++ / ++shift+c++ | Copy value / copy a code reference (dbutils, Spark conf, CLI) |
| ++r++ / ++shift+r++ | Refresh scope / workspace |
| ++a++ / ++shift+a++ | Authorization overview / stale-secret audit |
| ++w++ · ++ctrl+p++ | Switch workspace · command palette |
| ++question++ · ++q++ | Help · quit |

## Filtering

Press ++slash++ to fuzzy-filter the focused pane. While the filter bar is open, ++up++ ++down++ still move the table cursor, so you can narrow and pick in one motion. ++enter++ keeps the filter and returns to the table — a `⌕ query n/m` chip above the table shows what's active — and ++esc++ clears it. A filter survives a refresh; switching scope clears the secrets filter.

## Sorting

Every table sorts the same way: ++s++ advances to the next column (ascending), ++shift+s++ reverses the direction, and clicking a column header works too. A ↑ / ↓ marks the active column.

## Read-only mode

Start with `isolinear --read-only` to browse, reveal, search, and copy with every mutation disabled — the mutating keys disappear from the footer and the permissions editor becomes view-only. The header shows a `read-only` marker.
