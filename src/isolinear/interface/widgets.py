"""The three browser panes as self-contained widgets.

Each pane owns its rendering + a fuzzy filter, and re-emits a domain-level
message (`ScopesPane.Selected`, `SecretsPane.Selected`) so the screen stays thin.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from ..domain import Acl, Scope, Secret


def fuzzy_match(query: str, text: str) -> bool:
    """Case-insensitive subsequence match (the chars appear in order)."""
    query = query.lower()
    if not query:
        return True
    it = iter(text.lower())
    return all(ch in it for ch in query)


def relative_age(ms: int | None) -> tuple[str, bool]:
    """Return (human age, is_fresh<7d). e.g. ('2d', True)."""
    if not ms:
        return "—", False
    secs = max(0, time.time() - ms / 1000)
    fresh = secs < 7 * 86400
    for unit, n in (("y", 31536000), ("mo", 2592000), ("d", 86400), ("h", 3600)):
        if secs >= n:
            return f"{int(secs // n)}{unit}", fresh
    if secs >= 60:
        return f"{int(secs // 60)}m", fresh
    return "now", True


@dataclass
class ScopeRow:
    """View model for one scope row."""

    name: str
    icon: str
    count: int
    access: str  # MANAGE | WRITE | READ | "—"


class ScopesPane(Vertical):
    """Left pane: the scope list (filterable, with counts + access)."""

    class Selected(Message):
        def __init__(self, scope: str) -> None:
            self.scope = scope
            super().__init__()

    def __init__(self) -> None:
        super().__init__(id="scopes-pane", classes="pane")
        self._rows: list[ScopeRow] = []
        self._visible: list[ScopeRow] = []
        self._filter = ""

    def compose(self) -> ComposeResult:
        yield Static("SCOPES", classes="pane-title", id="scopes-title")
        yield ListView(id="scopes-list")
        yield Static("", id="scopes-empty", classes="empty-hint")

    def show(
        self, rows: list[ScopeRow], *, keep: str | None = None, focus: bool = True
    ) -> None:
        self._rows = rows
        self._filter = ""
        self._rebuild(focus=focus, keep=keep)

    def apply_filter(self, text: str) -> None:
        self._filter = text
        self._rebuild(focus=False)

    def _rebuild(self, *, focus: bool, keep: str | None = None) -> None:
        lv = self.query_one(ListView)
        lv.clear()
        self._visible = [r for r in self._rows if fuzzy_match(self._filter, r.name)]
        for r in self._visible:
            lv.append(ListItem(Label(f"{r.name}  [$text-muted]{r.count}[/]")))
        self.query_one("#scopes-title", Static).update(f"SCOPES  {len(self._rows)}")
        lv.display = bool(self._visible)
        hint = self.query_one("#scopes-empty", Static)
        hint.display = not self._visible
        if not self._rows:
            hint.update(
                "[$text-muted]No scopes yet.\nPress [b $primary]N[/] to create.[/]"
            )
        elif not self._visible:
            hint.update(f"[$text-muted]No scope matches\n“{self._filter}”.[/]")
        if self._visible:
            idx = next((i for i, r in enumerate(self._visible) if r.name == keep), 0)
            lv.index = idx
            if focus:
                lv.focus()

    @on(ListView.Highlighted, "#scopes-list")
    def _highlighted(self, event: ListView.Highlighted) -> None:
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self._visible):
            self.post_message(self.Selected(self._visible[idx].name))


class SecretsPane(Vertical):
    """Middle pane: the secrets in the selected scope (filterable)."""

    class Selected(Message):
        def __init__(self, key: str) -> None:
            self.key = key
            super().__init__()

    def __init__(self) -> None:
        super().__init__(id="secrets-pane", classes="pane")
        self._scope = ""
        self._secrets: list[Secret] = []
        self._filter = ""
        self._sort_col = 0  # column index: 0=Key, 1=Updated, 2=Age
        self._sort_rev = False

    def compose(self) -> ComposeResult:
        yield Static("SECRETS", classes="pane-title", id="secrets-title")
        table: DataTable = DataTable(id="secrets-table", zebra_stripes=False)
        table.cursor_type = "row"
        yield table
        yield Static("", id="secrets-empty", classes="empty-hint")

    def show(self, scope: str, secrets: list[Secret]) -> None:
        self._scope = scope
        self._secrets = secrets
        self._filter = ""
        self._rebuild()

    def apply_filter(self, text: str) -> None:
        self._filter = text
        self._rebuild()

    def _rebuild(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        arrow = "↓" if self._sort_rev else "↑"
        table.add_columns(
            *(
                f"{name} {arrow}" if i == self._sort_col else name
                for i, name in enumerate(("Key", "Updated", "Age"))
            )
        )
        visible = self._sorted(
            [s for s in self._secrets if fuzzy_match(self._filter, s.key)]
        )
        for s in visible:
            age, _ = relative_age(s.last_updated_ms)
            table.add_row(
                s.key,
                Text(s.last_updated, style="grey62"),
                Text(age, style="grey50"),
                key=s.key,
            )
        title = f"SECRETS  {self._scope} · {len(visible)}" if self._scope else "SECRETS"
        self.query_one("#secrets-title", Static).update(title)
        table.display = bool(visible)
        hint = self.query_one("#secrets-empty", Static)
        hint.display = not visible and bool(self._scope)
        if not visible and self._scope:
            if self._filter:
                hint.update(f"[$text-muted]No secret matches\n“{self._filter}”.[/]")
            else:
                hint.update(
                    f"[$text-muted]“{self._scope}” is empty.\n"
                    "Press [b $primary]n[/] to add a secret.[/]"
                )

    def clear(self) -> None:
        self._scope = ""
        self._secrets = []
        self.query_one(DataTable).clear()
        self.query_one("#secrets-title", Static).update("SECRETS")
        self.query_one("#secrets-empty").display = False

    def focus_table(self) -> None:
        self.query_one(DataTable).focus()

    @on(DataTable.RowHighlighted, "#secrets-table")
    def _highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value:
            self.post_message(self.Selected(event.row_key.value))

    # ── sorting: click a column header, or cycle with the `s` key ──────
    @on(DataTable.HeaderSelected, "#secrets-table")
    def _header_clicked(self, event: DataTable.HeaderSelected) -> None:
        self._set_sort(event.column_index)

    def cycle_sort(self) -> None:
        """Keyboard sort: flip direction, then advance to the next column."""
        if not self._sort_rev:
            self._sort_rev = True
        else:
            self._sort_rev = False
            self._sort_col = (self._sort_col + 1) % 3
        self._rebuild()

    def _set_sort(self, col: int) -> None:
        if col == self._sort_col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col, self._sort_rev = col, False
        self._rebuild()

    def _sorted(self, secrets: list[Secret]) -> list[Secret]:
        if self._sort_col == 0:  # Key — alphabetical
            return sorted(secrets, key=lambda s: s.key.lower(), reverse=self._sort_rev)
        # Updated / Age — by timestamp
        return sorted(
            secrets, key=lambda s: s.last_updated_ms or 0, reverse=self._sort_rev
        )


class DetailPane(Vertical):
    """Right pane: metadata + ACLs for the selection, and the secret value."""

    def __init__(self) -> None:
        super().__init__(id="detail-pane", classes="pane")

    def compose(self) -> ComposeResult:
        yield Static("DETAIL", classes="pane-title")
        with VerticalScroll():
            yield Static("", id="detail-body")
            yield Static("", id="detail-value", classes="secret-value")

    def _body(self, markup: str) -> None:
        self.query_one("#detail-body", Static).update(markup)

    def _hide_value(self) -> None:
        self.query_one("#detail-value").display = False

    def show_value(self, value: str) -> None:
        """Reveal the value instantly in the live (green) card."""
        card = self.query_one("#detail-value", Static)
        card.display = True
        card.update(value)

    def clear(self) -> None:
        """The 'nothing selected' state."""
        self._hide_value()
        self._body(
            "\n[$text-muted]Nothing selected.[/]"
            "\n[$text-muted]Pick a scope on the left.[/]"
        )

    def show_scope(
        self, scope: Scope, secret_count: int, acls: list[Acl], access: str
    ) -> None:
        self._hide_value()
        backend = "Azure Key Vault" if scope.is_keyvault else "Databricks-backed"
        access_text = access if access != "—" else "none"
        lines = [
            f"[b]{scope.name}[/]",
            "",
            f"[$text-muted]Backend[/]      {backend}",
            f"[$text-muted]Secrets[/]      {secret_count}",
            f"[$text-muted]Your access[/]  {access_text}",
            "",
            f"[$text-muted]Permissions[/]  [dim]{len(acls)}[/]",
        ]
        if acls:
            for acl in acls:
                lines.append(f"  {acl.principal}  [$text-muted]{acl.permission}[/]")
        else:
            lines.append("  [$text-muted](none)[/]")
        lines += ["", "[$text-muted]p to manage permissions[/]"]
        self._body("\n".join(lines))

    def show_secret(
        self, secret: Secret | None, scope: str, key: str, value: str | None
    ) -> None:
        updated = secret.last_updated if secret else "—"
        age = relative_age(secret.last_updated_ms)[0] if secret else "—"
        lines = [
            f"[b]{key}[/]",
            "",
            f"[$text-muted]Scope[/]     {scope}",
            f"[$text-muted]Updated[/]   {updated} [dim]({age} ago)[/]",
            "",
        ]
        if value is not None:
            lines += [
                "[$text-muted]Value[/]     [$accent]revealed[/]",
                "[dim]space to hide · c to copy[/]",
            ]
            self._body("\n".join(lines))
            self.show_value(value)
        else:
            lines += [
                "[$text-muted]Value[/]     [dim]••••••••[/]",
                "[dim]space to reveal[/]",
            ]
            self._hide_value()
            self._body("\n".join(lines))
