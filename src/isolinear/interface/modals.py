"""Generic modal dialogs: confirm, secret/scope forms, permissions, help, auth."""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Select, Static

from ..application import WorkspaceService
from ..domain import AuthSummary, Identity, StoreError

PERMISSIONS = ["READ", "WRITE", "MANAGE"]


class ConfirmModal(ModalScreen[bool]):
    """Yes/No guard for destructive actions."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
    ]

    def __init__(self, title: str, message: str, danger: bool = True) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self._danger = danger

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="danger" if self._danger else ""):
            yield Static(self._title, classes="dialog-title")
            yield Static(self._message)
            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel", variant="default")
                yield Button(
                    "Delete" if self._danger else "OK",
                    id="ok",
                    variant="error" if self._danger else "primary",
                )

    @on(Button.Pressed, "#ok")
    def action_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(False)


class SecretFormModal(ModalScreen[tuple[str, str] | None]):
    """Create or edit a secret. On edit, the key is fixed."""

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
            yield Static(f"{verb}  ·  scope “{self._scope}”", classes="dialog-title")
            key_input = Input(value=self._key, placeholder="key", id="f-key")
            key_input.disabled = self._edit
            yield key_input
            yield Input(
                value=self._value,
                placeholder="value",
                password=True,
                id="f-value",
            )
            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Save", id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#f-value" if self._edit else "#f-key", Input).focus()

    @on(Button.Pressed, "#ok")
    @on(Input.Submitted)
    def _save(self) -> None:
        key = self.query_one("#f-key", Input).value.strip()
        value = self.query_one("#f-value", Input).value
        if not key:
            self.query_one("#f-key", Input).focus()
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


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,q,?", "close", "Close")]

    KEYS = [
        ("↑↓ / j k", "Move within a pane"),
        ("←→ / h l", "Move between panes"),
        ("tab", "Next pane"),
        ("g / G", "Jump to top / bottom"),
        ("enter", "Drill scope → secrets"),
        ("/", "Filter the focused pane"),
        ("s", "Sort secrets (or click a column)"),
        ("", ""),
        ("n / N", "New secret / new scope"),
        ("e", "Edit secret value"),
        ("d", "Delete secret/scope (confirm)"),
        ("p", "Manage scope permissions (ACLs)"),
        ("space", "Reveal / hide value"),
        ("c", "Copy value to clipboard"),
        ("", ""),
        ("r / R", "Refresh scope / workspace"),
        ("a", "Authorization overview"),
        ("w", "Switch / add workspace (login)"),
        ("ctrl+p", "Command palette"),
        ("? / q", "Help / quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Isolinear — keys", classes="dialog-title")
            with VerticalScroll():
                for key, desc in self.KEYS:
                    yield Static(f"[b $primary]{key:<12}[/]  {desc}")

    def action_close(self) -> None:
        self.dismiss(None)


class AuthScreen(ModalScreen[None]):
    """Authorization overview (US-13)."""

    BINDINGS = [Binding("escape,q,a", "close", "Close")]

    def __init__(self, identity: Identity, summaries: list[AuthSummary]) -> None:
        super().__init__()
        self._identity = identity
        self._summaries = summaries

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Authorization overview", classes="dialog-title")
            who = self._identity.user_name or "(unknown)"
            status = (
                "✓ authenticated"
                if self._identity.authenticated
                else "✗ not authenticated"
            )
            yield Static(f"[$text-muted]Identity[/]  [b]{who}[/]   [$primary]{status}[/]")
            table: DataTable = DataTable(id="auth-table", zebra_stripes=False)
            table.cursor_type = "row"
            table.add_columns("Scope", "My access", "ACLs", "Write", "Manage")
            for s in self._summaries:
                table.add_row(
                    s.scope,
                    s.effective,
                    str(s.acl_count),
                    "✓" if s.can_write else "·",
                    "✓" if s.can_manage else "·",
                )
            yield table

    def on_mount(self) -> None:
        self.query_one(DataTable).focus()

    def action_close(self) -> None:
        self.dismiss(None)


class AclFormModal(ModalScreen[tuple[str, str] | None]):
    """Grant or change a principal's permission on a scope."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self, principal: str = "", permission: str = "READ", edit: bool = False
    ) -> None:
        super().__init__()
        self._principal = principal
        self._permission = permission if permission in PERMISSIONS else "READ"
        self._edit = edit

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            verb = "Change permission" if self._edit else "Grant permission"
            yield Static(verb, classes="dialog-title")
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
    ]

    def __init__(self, session: WorkspaceService, scope: str) -> None:
        super().__init__()
        self._session = session
        self._scope = scope
        self._principals: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(f"Permissions — {self._scope}", classes="dialog-title")
            yield Static("[$text-muted]a add · e change · d remove · esc close[/]")
            table: DataTable = DataTable(id="acl-table", zebra_stripes=False)
            table.cursor_type = "row"
            table.add_columns("Principal", "Permission")
            yield table

    def on_mount(self) -> None:
        self._populate()
        self.query_one(DataTable).focus()

    def _populate(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._principals = []
        for acl in self._session.acls_for(self._scope):
            table.add_row(acl.principal, acl.permission, key=acl.principal)
            self._principals.append(acl.principal)

    def _selected(self) -> str | None:
        table = self.query_one(DataTable)
        row = table.cursor_row
        if 0 <= row < len(self._principals):
            return self._principals[row]
        return None

    def action_add(self) -> None:
        self.app.push_screen(AclFormModal(), self._on_form)

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
        if principal:
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
