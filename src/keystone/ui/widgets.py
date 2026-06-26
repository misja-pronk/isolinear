"""The three browser panes as self-contained widgets.

Each pane owns its own rendering and re-emits a domain-level message
(`ScopesPane.Selected`, `SecretsPane.Selected`) so the screen can stay thin and
just translate selections into session calls.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from ..core import Acl, Scope, Secret

PERM_COLOR = {"READ": "$secondary", "WRITE": "$success", "MANAGE": "$accent"}

# An arch with its keystone (cyan) — greets you before anything is selected.
ARCH = """\
[$secondary]         ▟██▙[/]
[$primary]      ▟█▘    ▝█▙[/]
[$primary]    ▟█▘        ▝█▙[/]
[$primary]   ██            ██[/]
[$primary]   ██            ██[/]"""


class ScopesPane(Vertical):
    """Left pane: the scope list."""

    class Selected(Message):
        def __init__(self, scope: str) -> None:
            self.scope = scope
            super().__init__()

    def __init__(self) -> None:
        super().__init__(id="scopes-pane", classes="pane")
        self._scopes: list[Scope] = []

    def compose(self) -> ComposeResult:
        yield Static("🔒  SCOPES", classes="pane-title")
        yield ListView(id="scopes-list")
        yield Static(
            "[$text-muted]No scopes yet.\nPress [b $primary]N[/] to create one.[/]",
            id="scopes-empty",
            classes="empty-hint",
        )

    def show(self, scopes: list[Scope]) -> None:
        self._scopes = scopes
        lv = self.query_one(ListView)
        lv.clear()
        for scope in scopes:
            lv.append(ListItem(Label(f"{scope.icon}  {scope.name}")))
        empty = not scopes
        lv.display = not empty
        self.query_one("#scopes-empty").display = empty
        if scopes:
            lv.index = 0
            lv.focus()

    @on(ListView.Highlighted, "#scopes-list")
    def _highlighted(self, event: ListView.Highlighted) -> None:
        idx = event.list_view.index
        if idx is not None and 0 <= idx < len(self._scopes):
            self.post_message(self.Selected(self._scopes[idx].name))


class SecretsPane(Vertical):
    """Middle pane: the secrets in the selected scope."""

    class Selected(Message):
        def __init__(self, key: str) -> None:
            self.key = key
            super().__init__()

    def __init__(self) -> None:
        super().__init__(id="secrets-pane", classes="pane")

    def compose(self) -> ComposeResult:
        yield Static("🔑  SECRETS", classes="pane-title", id="secrets-title")
        table: DataTable = DataTable(id="secrets-table", zebra_stripes=True)
        table.cursor_type = "row"
        yield table
        yield Static("", id="secrets-empty", classes="empty-hint")

    def on_mount(self) -> None:
        self.query_one(DataTable).add_columns("Key", "Last updated")

    def show(self, scope: str, secrets: list[Secret]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for s in secrets:
            table.add_row(s.key, s.last_updated, key=s.key)
        self.query_one("#secrets-title", Static).update(
            f"🔑  SECRETS · {scope} ({len(secrets)})"
        )
        empty = not secrets
        table.display = not empty
        hint = self.query_one("#secrets-empty", Static)
        hint.display = empty
        if empty:
            hint.update(
                f"[$text-muted]📭  “{scope}” is empty.\n"
                "Press [b $primary]n[/] to add a secret.[/]"
            )

    def clear(self) -> None:
        self.query_one(DataTable).clear()
        self.query_one("#secrets-title", Static).update("🔑  SECRETS")
        self.query_one("#secrets-empty").display = False

    def focus_table(self) -> None:
        self.query_one(DataTable).focus()

    @on(DataTable.RowHighlighted, "#secrets-table")
    def _highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value:
            self.post_message(self.Selected(event.row_key.value))


class DetailPane(Vertical):
    """Right pane: metadata + ACLs for the selection, and the secret value."""

    def __init__(self) -> None:
        super().__init__(id="detail-pane", classes="pane")

    def compose(self) -> ComposeResult:
        yield Static("ℹ  DETAIL", classes="pane-title")
        with VerticalScroll():
            yield Static("", id="detail-body")
            yield Static("", id="detail-value", classes="secret-value")

    def _body(self, markup: str) -> None:
        self.query_one("#detail-body", Static).update(markup)

    def _hide_value(self) -> None:
        self.query_one("#detail-value").display = False

    def show_value(self, value: str) -> None:
        card = self.query_one("#detail-value", Static)
        card.update(f"[$accent b]🔓 {value}[/]")
        card.display = True

    def clear(self) -> None:
        """The 'nothing selected' state — an empty arch, standing by."""
        self._hide_value()
        self._body(
            ARCH
            + "\n\n[$text-muted]   Standing by.[/]"
            + "\n[$text-muted]   Select a scope to inspect.[/]"
        )

    def show_scope(self, scope: Scope, secret_count: int, acls: list[Acl]) -> None:
        self._hide_value()
        backend = "Azure Key Vault" if scope.is_keyvault else "Databricks-backed"
        lines = [
            f"[$primary b]{scope.icon}  {scope.name}[/]",
            "",
            f"[$text-muted]backend[/]   [b]{backend}[/]",
            f"[$text-muted]secrets[/]   [b]{secret_count}[/]",
            "",
            "[$primary]👥 Permissions[/]",
        ]
        if acls:
            for acl in acls:
                color = PERM_COLOR.get(acl.permission, "$foreground")
                lines.append(f"  [b]{acl.principal}[/] [{color}]{acl.permission}[/]")
        else:
            lines.append("  [$text-muted](none / not yet loaded)[/]")
        lines.append("")
        lines.append("[dim]p to manage permissions[/]")
        self._body("\n".join(lines))

    def show_secret(
        self, secret: Secret | None, scope: str, key: str, value: str | None
    ) -> None:
        updated = secret.last_updated if secret else "—"
        lines = [
            f"[$primary b]🔑  {key}[/]",
            "",
            f"[$text-muted]scope[/]     [b]{scope}[/]",
            f"[$text-muted]updated[/]   [b]{updated}[/]",
            "",
        ]
        if value is not None:
            lines.append("[$text-muted]value[/]   [dim]space to hide · c to copy[/]")
            self._body("\n".join(lines))
            self.show_value(value)
        else:
            lines.append("[$text-muted]value[/]   [dim]•••••••• · space to reveal[/]")
            self._hide_value()
            self._body("\n".join(lines))
