"""Generic modal dialogs: confirm, secret/scope forms, permissions, help, auth."""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Select, Static

from ..application import WorkspaceService
from ..domain import (
    STALE_AFTER_DAYS,
    AuthSummary,
    Identity,
    Secret,
    StoreError,
    perm_rank,
)
from .sorting import SortState
from .widgets import ACL_SORT_KEYS, fuzzy_match, perm_cell, relative_age

PERMISSIONS = ["READ", "WRITE", "MANAGE"]


def key_label(label: str) -> str:
    """A button label with its first letter underlined as the access key."""
    return f"[u]{label[0]}[/u]{label[1:]}" if label else label


class ConfirmModal(ModalScreen[bool]):
    """Yes/No guard for destructive actions.

    Confirming takes a deliberate `y` — never the key that opened the dialog
    (e.g. `d` for delete), so a double-tap can't slip past the guard.
    """

    BINDINGS = [
        Binding("escape,c,n", "cancel", "Cancel"),
        Binding("y,o", "confirm", "Confirm"),
    ]

    def __init__(
        self, title: str, message: str, danger: bool = True, ok_label: str = ""
    ) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._danger = danger
        self._ok_label = ok_label or ("Delete" if danger else "OK")

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="danger" if self._danger else ""):
            yield Static(self._title, classes="dialog-title")
            yield Static(self._message)
            with Horizontal(classes="buttons"):
                yield Button(key_label("Cancel"), id="cancel", variant="default")
                # danger labels get no access-key underline: only `y` confirms
                yield Button(
                    self._ok_label if self._danger else key_label(self._ok_label),
                    id="ok",
                    variant="error" if self._danger else "primary",
                )
            yield Static("[$text-muted]y confirm · esc cancel[/]", classes="dialog-hint")

    @on(Button.Pressed, "#ok")
    def action_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(False)


class SecretFormModal(ModalScreen[tuple[str, str] | None]):
    """Create or edit a secret. On edit, the key is fixed.

    The value comes from the masked input OR from a file path — the file route
    exists because multiline values (PEM keys, certificates, JSON blobs) can't
    be typed into a single-line input.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self, scope: str, key: str = "", value: str = "", edit: bool = False
    ) -> None:
        super().__init__()
        self._scope = scope
        self._key = key
        self._value = value
        self._edit = edit

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            verb = "Edit secret" if self._edit else "New secret"
            yield Static(
                f"{verb}   [$scopes-color]{self._scope}[/]", classes="dialog-title"
            )
            key_input = Input(value=self._key, placeholder="key", id="f-key")
            key_input.disabled = self._edit
            yield key_input
            yield Input(
                value=self._value,
                placeholder="value",
                password=True,
                id="f-value",
            )
            yield Input(
                placeholder="…or a file to read the value from (~/certs/key.pem)",
                id="f-file",
            )
            yield Static("", id="form-error", classes="form-error")
            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#f-value" if self._edit else "#f-key", Input).focus()

    def _error(self, message: str) -> None:
        error = self.query_one("#form-error", Static)
        error.update(f"[$error]{escape(message)}[/]")
        error.display = True

    @on(Button.Pressed, "#ok")
    @on(Input.Submitted)
    def _save(self) -> None:
        key = self.query_one("#f-key", Input).value.strip()
        value = self.query_one("#f-value", Input).value
        file_path = self.query_one("#f-file", Input).value.strip()
        if not key:
            self.query_one("#f-key", Input).focus()
            return
        if value and file_path:
            self._error("Provide a value or a file — not both.")
            return
        if file_path:
            try:
                value = Path(file_path).expanduser().read_text()
            except OSError as exc:
                self._error(f"Cannot read file: {exc}")
                return
        if not value:
            # an empty value on edit would silently wipe the secret
            self._error("Enter a value, or a file to read it from.")
            self.query_one("#f-value", Input).focus()
            return
        self.dismiss((key, value))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class ScopeFormModal(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("New scope", classes="dialog-title")
            yield Input(placeholder="scope name", id="f-scope")
            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Create", id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#f-scope", Input).focus()

    @on(Button.Pressed, "#ok")
    @on(Input.Submitted)
    def _save(self) -> None:
        name = self.query_one("#f-scope", Input).value.strip()
        if name:
            self.dismiss(name)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class SearchModal(ModalScreen[tuple[str, str] | None]):
    """Global search: fuzzy-match `scope/key` across the whole workspace.

    Everything is already warmed into the read model, so matching is local and
    instant. Dismisses with the chosen (scope, key) for the browser to jump to.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("down", "move(1)", "Down", show=False),
        Binding("up", "move(-1)", "Up", show=False),
    ]

    def __init__(self, entries: list[tuple[str, str]]) -> None:
        super().__init__()
        self._entries = entries  # (scope, key)
        self._visible: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Search all scopes", classes="dialog-title")
            yield Input(placeholder="scope/key…", id="f-search")
            table: DataTable = DataTable(id="search-results", zebra_stripes=False)
            table.cursor_type = "row"
            table.can_focus = False  # the input keeps focus; ↑↓ drive the table
            yield table
            yield Static(
                "[$text-muted]↑↓ move · enter open · esc close[/]",
                classes="dialog-hint",
            )

    def on_mount(self) -> None:
        self._populate("")
        self.query_one(Input).focus()

    def _populate(self, query: str) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns("Scope", "Key")
        scope_color = self.app.theme_variables.get("scopes-color", "")
        self._visible = [e for e in self._entries if fuzzy_match(query, f"{e[0]}/{e[1]}")]
        for scope, key in self._visible:
            table.add_row(Text(scope, style=scope_color), key)
        table.display = bool(self._visible)

    @on(Input.Changed, "#f-search")
    def _changed(self, event: Input.Changed) -> None:
        self._populate(event.value)

    def action_move(self, step: int) -> None:
        table = self.query_one(DataTable)
        if step > 0:
            table.action_cursor_down()
        else:
            table.action_cursor_up()

    @on(Input.Submitted, "#f-search")
    def _open(self) -> None:
        row = self.query_one(DataTable).cursor_row
        if 0 <= row < len(self._visible):
            self.dismiss(self._visible[row])

    @on(DataTable.RowSelected, "#search-results")
    def _clicked(self, event: DataTable.RowSelected) -> None:
        if 0 <= event.cursor_row < len(self._visible):
            self.dismiss(self._visible[event.cursor_row])

    def action_cancel(self) -> None:
        self.dismiss(None)


class SnippetModal(ModalScreen[str | None]):
    """Pick a code reference to a secret; returns the snippet to copy."""

    BINDINGS = [
        Binding("escape,q", "cancel", "Cancel"),
        Binding("j", "move(1)", "Down", show=False),
        Binding("k", "move(-1)", "Up", show=False),
    ]

    def __init__(self, scope: str, key: str) -> None:
        super().__init__()
        self._options: list[tuple[str, str]] = [
            ("Python (dbutils)", f'dbutils.secrets.get(scope="{scope}", key="{key}")'),
            ("Spark conf / job", f"{{{{secrets/{scope}/{key}}}}}"),
            ("Databricks CLI", f"databricks secrets get-secret {scope} {key}"),
        ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Copy reference", classes="dialog-title")
            table: DataTable = DataTable(id="snippet-table", zebra_stripes=False)
            table.cursor_type = "row"
            yield table
            yield Static("[$text-muted]enter copy · esc close[/]", classes="dialog-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Format", "Snippet")
        for label, snippet in self._options:
            table.add_row(Text(label, style="bold"), Text(snippet))
        table.focus()

    def action_move(self, step: int) -> None:
        table = self.query_one(DataTable)
        if step > 0:
            table.action_cursor_down()
        else:
            table.action_cursor_up()

    @on(DataTable.RowSelected, "#snippet-table")
    def _picked(self, event: DataTable.RowSelected) -> None:
        self.dismiss(self._options[event.cursor_row][1])

    def action_cancel(self) -> None:
        self.dismiss(None)


class AuditScreen(ModalScreen[tuple[str, str] | None]):
    """Stale-secret audit: every secret not updated within the threshold.

    Pure view over the warmed metadata — no values are read. Enter dismisses
    with the chosen (scope, key) so the browser can jump to it; `c` copies the
    table as markdown for a rotation ticket.
    """

    THRESHOLDS = (30, 90, 180, 365)

    BINDINGS = [
        Binding("escape,q", "close", "Close"),
        Binding("t", "threshold", "Threshold"),
        Binding("c", "copy_report", "Copy report"),
        Binding("s", "sort", "Sort", show=False),
        Binding("S", "sort_reverse", "Sort reverse", show=False),
    ]

    def __init__(self, secrets: list[Secret], threshold: int = STALE_AFTER_DAYS) -> None:
        super().__init__()
        self._secrets = secrets
        self.threshold = threshold  # public: the browser persists it on close
        self._visible: list[Secret] = []
        # 0=Scope, 1=Key, 2=Updated/Age (one timestamp); default oldest first
        self._sort = SortState(3, col=2)

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Stale secrets", classes="dialog-title")
            yield Static("", id="audit-count")
            table: DataTable = DataTable(id="audit-table", zebra_stripes=False)
            table.cursor_type = "row"
            yield table
            yield Static(
                "[$text-muted]t threshold · enter open · c copy report "
                "· s/S sort · esc close[/]",
                classes="dialog-hint",
            )

    def on_mount(self) -> None:
        self._populate()
        self.query_one(DataTable).focus()

    def _sorted(self) -> list[Secret]:
        stale = [s for s in self._secrets if s.is_stale(self.threshold)]
        keys = (
            lambda s: (s.scope.lower(), s.key.lower()),
            lambda s: s.key.lower(),
            lambda s: s.last_updated_ms or 0,
        )
        return self._sort.apply(stale, keys)

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns(*self._sort.labels(("Scope", "Key", "Updated", "Age")))
        scope_color = self.app.theme_variables.get("scopes-color", "")
        warn = self.app.theme_variables.get("warning", "")
        self._visible = self._sorted()
        for s in self._visible:
            age, _ = relative_age(s.last_updated_ms)
            table.add_row(
                Text(s.scope, style=scope_color),
                s.key,
                Text(s.last_updated, style="grey62"),
                Text(age, style=warn),
            )
        table.display = bool(self._visible)
        self.query_one("#audit-count", Static).update(
            f"[$text-muted]{len(self._visible)} of {len(self._secrets)} secrets "
            f"not updated in [b]{self.threshold}d[/].[/]"
        )

    def action_threshold(self) -> None:
        """Cycle the staleness window: 30 → 90 → 180 → 365 days."""
        thresholds = self.THRESHOLDS
        i = thresholds.index(self.threshold) if self.threshold in thresholds else 0
        self.threshold = thresholds[(i + 1) % len(thresholds)]
        self._populate()

    def action_copy_report(self) -> None:
        if not self._visible:
            self.notify("Nothing to copy.")
            return
        lines = ["| Scope | Key | Updated | Age |", "|---|---|---|---|"]
        for s in self._visible:
            age, _ = relative_age(s.last_updated_ms)
            lines.append(f"| {s.scope} | {s.key} | {s.last_updated} | {age} |")
        self.app.copy_to_clipboard("\n".join(lines))
        self.notify(f"Copied {len(self._visible)} rows as markdown.")

    def action_sort(self) -> None:
        self._sort.cycle()
        self._populate()

    def action_sort_reverse(self) -> None:
        self._sort.flip()
        self._populate()

    @on(DataTable.HeaderSelected, "#audit-table")
    def _sort_by_header(self, event: DataTable.HeaderSelected) -> None:
        self._sort.click(event.column_index)  # Updated + Age share the timestamp
        self._populate()

    @on(DataTable.RowSelected, "#audit-table")
    def _open(self, event: DataTable.RowSelected) -> None:
        if 0 <= event.cursor_row < len(self._visible):
            chosen = self._visible[event.cursor_row]
            self.dismiss((chosen.scope, chosen.key))

    def action_close(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,q,?", "close", "Close")]

    KEYS = [
        ("↑↓ / j k", "Move within a pane"),
        ("←→ / h l", "Move between panes"),
        ("tab", "Next pane"),
        ("g / G", "Jump to top / bottom"),
        ("enter", "Scopes: open · Secrets: reveal"),
        ("/", "Filter the focused pane (↑↓ move while typing)"),
        ("ctrl+f", "Search every scope"),
        ("esc", "Clear the filter"),
        ("f", "Scopes: only mine / all"),
        ("s / S", "Sort: next column / reverse"),
        ("", ""),
        ("n / N", "New secret / new scope"),
        ("e", "Edit secret value"),
        ("d", "Delete secret/scope (confirm)"),
        ("u", "Undo the last secret delete"),
        ("p", "Manage scope permissions (ACLs)"),
        ("space", "Reveal / hide value (auto-hides in 30s)"),
        ("c / C", "Copy value / copy code reference"),
        ("", ""),
        ("r / R", "Refresh scope / workspace"),
        ("a", "Authorization overview"),
        ("A", "Audit: stale secrets"),
        ("w", "Switch / add workspace (login)"),
        ("ctrl+p", "Command palette"),
        ("? / q", "Help / quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Isolinear — keys", classes="dialog-title")
            with VerticalScroll():
                for key, desc in self.KEYS:
                    yield Static(f"[b $secondary]{key:<12}[/]  {desc}")
            yield Static("[$text-muted]esc close[/]", classes="dialog-hint")

    def action_close(self) -> None:
        self.dismiss(None)


class AuthScreen(ModalScreen[None]):
    """Authorization overview (US-13)."""

    BINDINGS = [
        Binding("escape,q,a", "close", "Close"),
        Binding("s", "sort", "Sort", show=False),
        Binding("S", "sort_reverse", "Sort reverse", show=False),
    ]

    def __init__(self, identity: Identity, summaries: list[AuthSummary]) -> None:
        super().__init__()
        self._identity = identity
        self._summaries = summaries
        # 0=Scope, 1=Your access, 2=Principals; default: highest access first
        self._sort = SortState(3, col=1, rev=True)

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Authorization overview", classes="dialog-title")
            who = self._identity.user_name or "(unknown)"
            status = (
                "[$success]✓ authenticated[/]"
                if self._identity.authenticated
                else "[$error]✗ not authenticated[/]"
            )
            yield Static(f"[$text-muted]Identity[/]  [b]{who}[/]   {status}")
            table: DataTable = DataTable(id="auth-table", zebra_stripes=False)
            table.cursor_type = "row"
            yield table
            yield Static("[$text-muted]s/S sort · esc close[/]", classes="dialog-hint")

    def on_mount(self) -> None:
        self._populate()
        self.query_one(DataTable).focus()

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns(*self._sort.labels(("Scope", "Your access", "Principals")))
        scope_color = self.app.theme_variables.get("scopes-color", "")
        keys = (
            lambda s: s.scope.lower(),
            lambda s: (perm_rank(s.effective), s.scope.lower()),
            lambda s: (s.acl_count, s.scope.lower()),
        )
        for s in self._sort.apply(self._summaries, keys):
            table.add_row(
                Text(s.scope, style=scope_color),
                perm_cell(self.app, s.effective),
                str(s.acl_count),
            )

    def action_sort(self) -> None:
        self._sort.cycle()
        self._populate()

    def action_sort_reverse(self) -> None:
        self._sort.flip()
        self._populate()

    @on(DataTable.HeaderSelected, "#auth-table")
    def _sort_by_header(self, event: DataTable.HeaderSelected) -> None:
        self._sort.click(event.column_index)
        self._populate()

    def action_close(self) -> None:
        self.dismiss(None)


class AclFormModal(ModalScreen[tuple[str, str] | None]):
    """Grant or change a principal's permission on a scope."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        principal: str = "",
        permission: str = "READ",
        edit: bool = False,
        scope: str = "",
    ) -> None:
        super().__init__()
        self._principal = principal
        self._permission = permission if permission in PERMISSIONS else "READ"
        self._edit = edit
        self._scope = scope

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="scope"):
            verb = "Change permission" if self._edit else "Grant permission"
            title = f"{verb}   [$scopes-color]{self._scope}[/]" if self._scope else verb
            yield Static(title, classes="dialog-title")
            principal = Input(
                value=self._principal,
                placeholder="principal (user, group, or service principal)",
                id="f-principal",
            )
            principal.disabled = self._edit
            yield principal
            yield Select(
                [(p, p) for p in PERMISSIONS],
                value=self._permission,
                id="f-permission",
                allow_blank=False,
            )
            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="ok", variant="primary")

    def on_mount(self) -> None:
        target = "#f-permission" if self._edit else "#f-principal"
        self.query_one(target).focus()

    @on(Button.Pressed, "#ok")
    @on(Input.Submitted)
    def _save(self) -> None:
        principal = self.query_one("#f-principal", Input).value.strip()
        permission = self.query_one("#f-permission", Select).value
        if not principal:
            self.query_one("#f-principal", Input).focus()
            return
        self.dismiss((principal, str(permission)))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class PermissionsScreen(ModalScreen[None]):
    """Manage the ACLs on a scope — the 'update scope' surface (US-11/US-12).

    Operates directly against the session (mutations run in worker threads) and
    refreshes itself after each change, so it doubles as a live permissions view.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("a", "add", "Add"),
        Binding("e", "edit", "Edit"),
        Binding("d,delete,x", "remove", "Remove"),
        Binding("s", "sort", "Sort", show=False),
        Binding("S", "sort_reverse", "Sort reverse", show=False),
    ]

    def __init__(
        self, session: WorkspaceService, scope: str, read_only: bool = False
    ) -> None:
        super().__init__()
        self._session = session
        self._scope = scope
        self._read_only = read_only
        self._principals: list[str] = []
        # 0=Principal, 1=Access; default: highest access first
        self._sort = SortState(2, col=1, rev=True)

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="scope"):
            yield Static(
                f"Permissions   [$scopes-color]{self._scope}[/]", classes="dialog-title"
            )
            table: DataTable = DataTable(id="acl-table", zebra_stripes=False)
            table.cursor_type = "row"
            yield table
            hint = (
                "[$warning]read-only[/][$text-muted] · s/S sort · esc close[/]"
                if self._read_only
                else "[$text-muted]a add · e change · d remove · s/S sort · esc close[/]"
            )
            yield Static(hint, classes="dialog-hint")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        return not (self._read_only and action in ("add", "edit", "remove"))

    def on_mount(self) -> None:
        self._populate()
        self.query_one(DataTable).focus()

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        keep = self._selected()  # preserve the selection across a re-sort / refresh
        table.clear(columns=True)
        table.add_columns(*self._sort.labels(("Principal", "Access")))
        self._principals = []
        cursor = 0
        acls = list(self._session.acls_for(self._scope))
        for acl in self._sort.apply(acls, ACL_SORT_KEYS):
            table.add_row(
                acl.principal, perm_cell(self.app, acl.permission), key=acl.principal
            )
            if acl.principal == keep:
                cursor = len(self._principals)
            self._principals.append(acl.principal)
        if self._principals:
            table.move_cursor(row=cursor)

    def _selected(self) -> str | None:
        table = self.query_one(DataTable)
        row = table.cursor_row
        if 0 <= row < len(self._principals):
            return self._principals[row]
        return None

    def action_sort(self) -> None:
        self._sort.cycle()
        self._populate()

    def action_sort_reverse(self) -> None:
        self._sort.flip()
        self._populate()

    @on(DataTable.HeaderSelected, "#acl-table")
    def _sort_by_header(self, event: DataTable.HeaderSelected) -> None:
        self._sort.click(event.column_index)
        self._populate()

    def action_add(self) -> None:
        self.app.push_screen(AclFormModal(scope=self._scope), self._on_form)

    def action_edit(self) -> None:
        principal = self._selected()
        if not principal:
            return
        current = next(
            (a for a in self._session.acls_for(self._scope) if a.principal == principal),
            None,
        )
        self.app.push_screen(
            AclFormModal(
                principal=principal,
                permission=current.permission if current else "READ",
                edit=True,
                scope=self._scope,
            ),
            self._on_form,
        )

    def _on_form(self, result: tuple[str, str] | None) -> None:
        if result:
            self._set_acl(*result)

    @work(group="acl")
    async def _set_acl(self, principal: str, permission: str) -> None:
        try:
            await asyncio.to_thread(
                self._session.set_acl, self._scope, principal, permission
            )
        except StoreError as exc:
            self.notify(f"Failed: {exc}", severity="error")
            return
        self._populate()
        self.notify(f"{principal} → {permission}")

    def action_remove(self) -> None:
        principal = self._selected()
        if not principal:
            return
        message = (
            f"Revoke [b]{escape(principal)}[/]'s access to [b]{escape(self._scope)}[/]."
        )
        if principal == self._session.identity.user_name:
            message += "\n[$warning]This is you — you may lose access to this scope.[/]"
        self.app.push_screen(
            ConfirmModal("Remove access", message, ok_label="Remove"),
            partial(self._remove_acl_if, principal),
        )

    def _remove_acl_if(self, principal: str, confirmed: bool | None) -> None:
        if confirmed:
            self._remove_acl(principal)

    @work(group="acl")
    async def _remove_acl(self, principal: str) -> None:
        try:
            await asyncio.to_thread(self._session.remove_acl, self._scope, principal)
        except StoreError as exc:
            self.notify(f"Failed: {exc}", severity="error")
            return
        self._populate()
        self.notify(f"Removed {principal}")

    def action_close(self) -> None:
        self.dismiss(None)
