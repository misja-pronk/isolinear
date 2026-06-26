"""The three browser panes as self-contained widgets.

Each pane owns its rendering + a fuzzy filter, and re-emits a domain-level
message (`ScopesPane.Selected`, `SecretsPane.Selected`) so the screen stays thin.
"""

from __future__ import annotations

import random
import string
import time
from dataclasses import dataclass

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from ..domain import Acl, Scope, Secret

PERM_COLOR = {"READ": "$secondary", "WRITE": "$success", "MANAGE": "$accent"}
# A compact glyph for the current user's access on a scope.
ACCESS_GLYPH = {
    "MANAGE": "[$accent]★[/]",
    "WRITE": "[$success]✎[/]",
    "READ": "[$secondary]•[/]",
}

# An arch with its keystone (cyan) — greets you before anything is selected.
ARCH = """\
[$secondary]         ▟██▙[/]
[$primary]      ▟█▘    ▝█▙[/]
[$primary]    ▟█▘        ▝█▙[/]
[$primary]   ██            ██[/]
[$primary]   ██            ██[/]"""


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
        yield Static("🔒  SCOPES", classes="pane-title", id="scopes-title")
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
            glyph = ACCESS_GLYPH.get(r.access, "")
            lv.append(ListItem(Label(f"{r.icon}  {r.name}  [dim]{r.count}[/] {glyph}")))
        self.query_one("#scopes-title", Static).update(f"🔒  SCOPES ({len(self._rows)})")
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

    def compose(self) -> ComposeResult:
        yield Static("🔑  SECRETS", classes="pane-title", id="secrets-title")
        table: DataTable = DataTable(id="secrets-table", zebra_stripes=True)
        table.cursor_type = "row"
        yield table
        yield Static("", id="secrets-empty", classes="empty-hint")

    def on_mount(self) -> None:
        self.query_one(DataTable).add_columns("Key", "Updated", "Age")

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
        table.clear()
        visible = [s for s in self._secrets if fuzzy_match(self._filter, s.key)]
        for s in visible:
            age, fresh = relative_age(s.last_updated_ms)
            table.add_row(
                s.key,
                Text(s.last_updated, style="grey70"),
                Text(age, style="#29e0c4" if fresh else "grey50"),
                key=s.key,
            )
        title = (
            f"🔑  SECRETS · {self._scope} ({len(visible)})"
            if self._scope
            else "🔑  SECRETS"
        )
        self.query_one("#secrets-title", Static).update(title)
        table.display = bool(visible)
        hint = self.query_one("#secrets-empty", Static)
        hint.display = not visible and bool(self._scope)
        if not visible and self._scope:
            if self._filter:
                hint.update(f"[$text-muted]No secret matches\n“{self._filter}”.[/]")
            else:
                hint.update(
                    f"[$text-muted]📭  “{self._scope}” is empty.\n"
                    "Press [b $primary]n[/] to add a secret.[/]"
                )

    def clear(self) -> None:
        self._scope = ""
        self._secrets = []
        self.query_one(DataTable).clear()
        self.query_one("#secrets-title", Static).update("🔑  SECRETS")
        self.query_one("#secrets-empty").display = False

    def focus_table(self) -> None:
        self.query_one(DataTable).focus()

    @on(DataTable.RowHighlighted, "#secrets-table")
    def _highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value:
            self.post_message(self.Selected(event.row_key.value))


_UNLOCK_POOL = string.ascii_letters + string.digits + "!@#$%^&*/.:_-+="


class DetailPane(Vertical):
    """Right pane: metadata + ACLs for the selection, and the secret value."""

    def __init__(self) -> None:
        super().__init__(id="detail-pane", classes="pane")
        self._unlock_timer = None

    def compose(self) -> ComposeResult:
        yield Static("ℹ  DETAIL", classes="pane-title")
        with VerticalScroll():
            yield Static("", id="detail-body")
            yield Static("", id="detail-value", classes="secret-value")

    def _body(self, markup: str) -> None:
        self.query_one("#detail-body", Static).update(markup)

    def _stop_unlock(self) -> None:
        if self._unlock_timer is not None:
            self._unlock_timer.stop()
            self._unlock_timer = None

    def _hide_value(self) -> None:
        self._stop_unlock()
        self.query_one("#detail-value").display = False

    def show_value(self, value: str) -> None:
        """Reveal the value with a left-to-right 'decrypt' animation."""
        card = self.query_one("#detail-value", Static)
        card.display = True
        self._stop_unlock()
        steps = max(4, min(len(value), 12))
        state = {"n": 0}

        def frame() -> None:
            state["n"] += 1
            shown = int(len(value) * state["n"] / steps)
            if state["n"] >= steps:
                card.update(f"[$accent b]🔓 {value}[/]")
                self._stop_unlock()
                return
            out = "".join(
                ch if (ch in " \n\t" or i < shown) else random.choice(_UNLOCK_POOL)
                for i, ch in enumerate(value)
            )
            card.update(f"[$accent b]🔓 {out}[/]")

        card.update(
            f"[$accent b]🔓 {''.join(random.choice(_UNLOCK_POOL) for _ in value)}[/]"
        )
        self._unlock_timer = self.set_interval(0.03, frame)

    def clear(self) -> None:
        """The 'nothing selected' state — an empty arch, standing by."""
        self._hide_value()
        self._body(
            ARCH
            + "\n\n[$text-muted]   Standing by.[/]"
            + "\n[$text-muted]   Select a scope to inspect.[/]"
        )

    def show_scope(
        self, scope: Scope, secret_count: int, acls: list[Acl], access: str
    ) -> None:
        self._hide_value()
        backend = "Azure Key Vault" if scope.is_keyvault else "Databricks-backed"
        access_markup = (
            f"[{PERM_COLOR.get(access, '$foreground')} b]{access}[/]"
            if access != "—"
            else "[$text-muted]none[/]"
        )
        lines = [
            f"[$primary b]{scope.icon}  {scope.name}[/]",
            "",
            f"[$text-muted]backend[/]      [b]{backend}[/]",
            f"[$text-muted]secrets[/]      [b]{secret_count}[/]",
            f"[$text-muted]your access[/]  {access_markup}",
            "",
            f"[$primary]👥 Permissions[/] [dim]({len(acls)})[/]",
        ]
        if acls:
            for acl in acls:
                color = PERM_COLOR.get(acl.permission, "$foreground")
                lines.append(f"  [b]{acl.principal}[/] [{color}]{acl.permission}[/]")
        else:
            lines.append("  [$text-muted](none / not yet loaded)[/]")
        lines += ["", "[dim]p to manage permissions[/]"]
        self._body("\n".join(lines))

    def show_secret(
        self, secret: Secret | None, scope: str, key: str, value: str | None
    ) -> None:
        updated = secret.last_updated if secret else "—"
        age = relative_age(secret.last_updated_ms)[0] if secret else "—"
        lines = [
            f"[$primary b]🔑  {key}[/]",
            "",
            f"[$text-muted]scope[/]     [b]{scope}[/]",
            f"[$text-muted]updated[/]   [b]{updated}[/] [dim]({age} ago)[/]",
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
