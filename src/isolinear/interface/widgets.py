"""The three browser panes as self-contained widgets.

Each pane owns its rendering + a fuzzy filter, and re-emits a domain-level
message (`ScopesPane.Selected`, `SecretsPane.Selected`) so the screen stays thin.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from rich.markup import escape
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Static

from ..domain import Acl, Scope, Secret, perm_rank


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


# Permission levels, coloured by privilege so elevated access is scannable.
PERM_COLOR = {
    "READ": "$text-muted",
    "WRITE": "$secrets-color",
    "MANAGE": "$detail-color",
}


def perm_markup(permission: str) -> str:
    """Content markup for a permission level, coloured by privilege."""
    color = PERM_COLOR.get(permission, "$foreground")
    weight = " b" if permission == "MANAGE" else ""
    return f"[{color}{weight}]{permission}[/]"


def perm_cell(app: App, permission: str) -> Text:
    """A DataTable cell for a permission level, coloured by privilege."""
    var = PERM_COLOR.get(permission, "$foreground").lstrip("$")
    color = app.theme_variables.get(var, "")
    style = f"bold {color}" if permission == "MANAGE" else color
    return Text(permission, style=style)


@dataclass
class ScopeRow:
    """View model for one scope row."""

    name: str
    count: int


class ScopesPane(Vertical):
    """Left pane: the scopes table (filterable, with secret counts)."""

    class Selected(Message):
        def __init__(self, scope: str) -> None:
            self.scope = scope
            super().__init__()

    def __init__(self) -> None:
        super().__init__(id="scopes-pane", classes="pane")
        self._rows: list[ScopeRow] = []
        self._visible: list[ScopeRow] = []
        self._filter = ""
        self._sort_col = 0  # 0=Scope, 1=Secrets
        self._sort_rev = False

    def compose(self) -> ComposeResult:
        table: DataTable = DataTable(id="scopes-table", zebra_stripes=False)
        table.cursor_type = "row"
        yield table
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
        table = self.query_one(DataTable)
        table.clear(columns=True)
        arrow = "↓" if self._sort_rev else "↑"
        table.add_columns(
            *(
                f"{name} {arrow}" if i == self._sort_col else name
                for i, name in enumerate(("Scope", "Secrets"))
            )
        )
        self._visible = self._sorted(
            [r for r in self._rows if fuzzy_match(self._filter, r.name)]
        )
        for r in self._visible:
            table.add_row(r.name, Text(str(r.count), style="grey62"), key=r.name)
        table.display = bool(self._visible)
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
            table.move_cursor(row=idx)
            if focus:
                table.focus()

    def focus_table(self) -> None:
        self.query_one(DataTable).focus()

    @on(DataTable.RowHighlighted, "#scopes-table")
    def _highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value:
            self.post_message(self.Selected(event.row_key.value))

    # ── sorting: click a column header, or cycle with the `s` key ──────
    @on(DataTable.HeaderSelected, "#scopes-table")
    def _header_clicked(self, event: DataTable.HeaderSelected) -> None:
        self._set_sort(event.column_index)

    def cycle_sort(self) -> None:
        """Keyboard sort: flip direction, then advance to the next column."""
        if not self._sort_rev:
            self._sort_rev = True
        else:
            self._sort_rev = False
            self._sort_col = (self._sort_col + 1) % 2
        self._rebuild(focus=False, keep=self._cursor_scope())

    def _set_sort(self, col: int) -> None:
        if col == self._sort_col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col, self._sort_rev = col, False
        self._rebuild(focus=False, keep=self._cursor_scope())

    def _cursor_scope(self) -> str | None:
        row = self.query_one(DataTable).cursor_row
        return self._visible[row].name if 0 <= row < len(self._visible) else None

    def _sorted(self, rows: list[ScopeRow]) -> list[ScopeRow]:
        if self._sort_col == 0:  # Scope — alphabetical
            return sorted(rows, key=lambda r: r.name.lower(), reverse=self._sort_rev)
        return sorted(rows, key=lambda r: r.count, reverse=self._sort_rev)  # Secrets


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
        self._visible: list[Secret] = []
        self._filter = ""
        self._sort_col = 0  # column index: 0=Key, 1=Updated, 2=Age
        self._sort_rev = False

    def compose(self) -> ComposeResult:
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

    def _rebuild(self, *, keep: str | None = None) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        arrow = "↓" if self._sort_rev else "↑"
        table.add_columns(
            *(
                f"{name} {arrow}" if i == self._sort_col else name
                for i, name in enumerate(("Key", "Updated", "Age"))
            )
        )
        self._visible = self._sorted(
            [s for s in self._secrets if fuzzy_match(self._filter, s.key)]
        )
        for s in self._visible:
            age, _ = relative_age(s.last_updated_ms)
            table.add_row(
                s.key,
                Text(s.last_updated, style="grey62"),
                Text(age, style="grey50"),
                key=s.key,
            )
        table.display = bool(self._visible)
        hint = self.query_one("#secrets-empty", Static)
        hint.display = not self._visible and bool(self._scope)
        if not self._visible and self._scope:
            if self._filter:
                hint.update(f"[$text-muted]No secret matches\n“{self._filter}”.[/]")
            else:
                hint.update(
                    f"[$text-muted]“{self._scope}” is empty.\n"
                    "Press [b $primary]n[/] to add a secret.[/]"
                )
        if self._visible and keep is not None:
            idx = next((i for i, s in enumerate(self._visible) if s.key == keep), 0)
            table.move_cursor(row=idx)

    def clear(self) -> None:
        self._scope = ""
        self._secrets = []
        self.query_one(DataTable).clear()
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
        self._rebuild(keep=self._cursor_key())

    def _set_sort(self, col: int) -> None:
        if col == self._sort_col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col, self._sort_rev = col, False
        self._rebuild(keep=self._cursor_key())

    def _cursor_key(self) -> str | None:
        row = self.query_one(DataTable).cursor_row
        return self._visible[row].key if 0 <= row < len(self._visible) else None

    def _sorted(self, secrets: list[Secret]) -> list[Secret]:
        if self._sort_col == 0:  # Key — alphabetical
            return sorted(secrets, key=lambda s: s.key.lower(), reverse=self._sort_rev)
        # Updated / Age — by timestamp
        return sorted(
            secrets, key=lambda s: s.last_updated_ms or 0, reverse=self._sort_rev
        )


class DetailPane(Vertical):
    """Right pane: metadata + a sortable ACL table for the selection, + the value."""

    def __init__(self) -> None:
        super().__init__(id="detail-pane", classes="pane")
        self._acls: list[Acl] = []
        self._sort_col = 1  # 0=Principal, 1=Access
        self._sort_rev = True  # Access, highest privilege first

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="detail-scroll", can_focus=False):
            yield Static("", id="detail-head")
            yield Static("", id="detail-perms")
            table: DataTable = DataTable(id="acl-table", zebra_stripes=False)
            table.cursor_type = "row"
            yield table
            yield Static("", id="detail-foot")
            yield Static("", id="detail-value", classes="secret-value")

    # ── section setters ─────────────────────────────────────────────
    def _head(self, markup: str) -> None:
        self.query_one("#detail-head", Static).update(markup)

    def _foot(self, markup: str) -> None:
        self.query_one("#detail-foot", Static).update(markup)

    def _hide_value(self) -> None:
        self.query_one("#detail-value").display = False

    def show_value(self, value: str) -> None:
        """Reveal the value instantly in the live (green) card."""
        card = self.query_one("#detail-value", Static)
        card.display = True
        card.update(escape(value))  # values are arbitrary — never parse as markup

    def clear(self) -> None:
        """The 'nothing selected' state."""
        self._acls = []
        self._hide_value()
        self.query_one("#detail-perms", Static).update("")
        self._foot("")
        self.query_one("#acl-table", DataTable).display = False
        self._head(
            "\n[$text-muted]Nothing selected.[/]"
            "\n[$text-muted]Pick a scope on the left.[/]"
        )

    def show_scope(
        self, scope: Scope, secret_count: int, acls: list[Acl], access: str
    ) -> None:
        self._hide_value()
        backend = "Azure Key Vault" if scope.is_keyvault else "Databricks-backed"
        access_text = perm_markup(access) if access != "—" else "[$text-muted]none[/]"
        self._head(
            "\n".join(
                [
                    f"[b $scopes-color]{escape(scope.name)}[/]",
                    "",
                    f"[$text-muted]Backend[/]      {backend}",
                    f"[$text-muted]Secrets[/]      {secret_count}",
                    f"[$text-muted]Your access[/]  {access_text}",
                ]
            )
        )
        self._show_acls(acls)
        self._foot("[$text-muted]p to manage permissions[/]")

    def show_secret(
        self,
        secret: Secret | None,
        scope: str,
        key: str,
        value: str | None,
        access: str = "—",
        acls: list[Acl] | None = None,
    ) -> None:
        acls = acls or []
        updated = secret.last_updated if secret else "—"
        access_text = perm_markup(access) if access != "—" else "[$text-muted]none[/]"
        self._head(
            "\n".join(
                [
                    f"[b $secrets-color]{escape(key)}[/]",
                    "",
                    f"[$text-muted]Scope[/]        [$scopes-color]{escape(scope)}[/]",
                    f"[$text-muted]Updated[/]      {updated}",
                    f"[$text-muted]Your access[/]  {access_text}",
                ]
            )
        )
        self._show_acls(acls)
        if value is not None:
            self._foot(
                "[$text-muted]Value[/]        [$value-color]revealed[/]\n"
                "[dim]space to hide · c to copy[/]"
            )
            self.show_value(value)
        else:
            self._foot(
                "[$text-muted]Value[/]        [dim]••••••••[/]\n[dim]space to reveal[/]"
            )
            self._hide_value()

    # ── the sortable ACL table ──────────────────────────────────────
    def _show_acls(self, acls: list[Acl]) -> None:
        self._acls = acls
        self.query_one("#detail-perms", Static).update(
            f"[$text-muted]Permissions[/]  [dim]{len(acls)}[/]"
        )
        self._populate_acls()

    def _populate_acls(self) -> None:
        table = self.query_one("#acl-table", DataTable)
        table.clear(columns=True)
        table.display = bool(self._acls)
        if not self._acls:
            return
        arrow = "↓" if self._sort_rev else "↑"
        cols = ("Principal", "Access")
        table.add_columns(
            *(f"{c} {arrow}" if i == self._sort_col else c for i, c in enumerate(cols))
        )
        for a in self._sorted_acls():
            table.add_row(a.principal, perm_cell(self.app, a.permission), key=a.principal)

    def _sorted_acls(self) -> list[Acl]:
        if self._sort_col == 0:  # Principal — alphabetical
            return sorted(
                self._acls, key=lambda a: a.principal.lower(), reverse=self._sort_rev
            )
        # Access — by privilege, then principal
        return sorted(
            self._acls,
            key=lambda a: (perm_rank(a.permission), a.principal.lower()),
            reverse=self._sort_rev,
        )

    def cycle_sort(self) -> None:
        """Keyboard sort: flip direction, then advance to the next column."""
        if not self._sort_rev:
            self._sort_rev = True
        else:
            self._sort_rev = False
            self._sort_col = (self._sort_col + 1) % 2
        self._populate_acls()

    @on(DataTable.HeaderSelected, "#acl-table")
    def _sort_by_header(self, event: DataTable.HeaderSelected) -> None:
        if event.column_index == self._sort_col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col, self._sort_rev = event.column_index, False
        self._populate_acls()
