"""MainScreen — the three-pane secret browser for one workspace session.

Holds no business logic: every operation is delegated to a `WorkspaceSession`
(run in a worker thread), and rendering is delegated to the pane widgets. The
screen's job is wiring — selections in, session calls out, results to panes.
"""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, ListView, Static

from ...core import (
    GatewayError,
    WorkspaceSession,
    auth,
    discover_workspaces,
)
from ..modals import (
    AuthScreen,
    ConfirmModal,
    HelpScreen,
    PermissionsScreen,
    ScopeFormModal,
    SecretFormModal,
)
from ..widgets import DetailPane, ScopesPane, SecretsPane
from .login import ConnectResult, LoginScreen


class VaultCommands(Provider):
    """Feeds every action into the command palette (ctrl+p)."""

    async def search(self, query: str) -> Hits:
        screen = self.screen
        if not isinstance(screen, MainScreen):
            return
        matcher = self.matcher(query)
        for label, action in screen.command_catalog():
            score = matcher.match(label)
            if score > 0:
                yield Hit(score, matcher.highlight(label), action, help=label)


class MainScreen(Screen[None]):
    COMMANDS = {VaultCommands}

    BINDINGS = [
        Binding("w", "switch_workspace", "Workspace"),
        Binding("n", "new_secret", "New"),
        Binding("N", "new_scope", "New scope", show=False),
        Binding("e", "edit_secret", "Edit"),
        Binding("d", "delete", "Delete"),
        Binding("p", "permissions", "Perms"),
        Binding("space", "reveal", "Reveal"),
        Binding("c", "copy", "Copy"),
        Binding("r", "refresh_scope", "Refresh"),
        Binding("R", "refresh_workspace", "Refresh all", show=False),
        Binding("a", "auth", "Auth"),
        Binding("question_mark", "help", "Help"),
        # navigation — vim + arrows, fully keyboard driven
        Binding("tab", "focus_next", "Next pane", show=False),
        Binding("right,l", "focus_pane('right')", "Pane →", show=False),
        Binding("left,h", "focus_pane('left')", "Pane ←", show=False),
        Binding("j,down", "vi('down')", "Down", show=False),
        Binding("k,up", "vi('up')", "Up", show=False),
        Binding("g", "jump('top')", "Top", show=False),
        Binding("G", "jump('bottom')", "Bottom", show=False),
    ]

    def __init__(self, profiles=None, session: WorkspaceSession | None = None) -> None:
        super().__init__()
        self.profiles = profiles if profiles is not None else []
        self.session = session
        self.current_scope: str | None = None
        self.current_secret: str | None = None
        self._revealed: tuple[str, str] | None = None

    # ── layout ─────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        with Horizontal(id="banner"):
            yield Static("🔒 VAULT", id="brand")
            yield Static("", id="ws-status")
        with Horizontal(id="body"):
            yield ScopesPane()
            yield SecretsPane()
            yield DetailPane()
        yield Footer()

    def on_mount(self) -> None:
        if self.session is not None:
            self.load(self.session)
        else:
            self.open_login()

    # ── pane accessors ─────────────────────────────────────────────────
    @property
    def scopes_pane(self) -> ScopesPane:
        return self.query_one(ScopesPane)

    @property
    def secrets_pane(self) -> SecretsPane:
        return self.query_one(SecretsPane)

    @property
    def detail_pane(self) -> DetailPane:
        return self.query_one(DetailPane)

    def _set_status(self, text: str) -> None:
        label = self.session.label if self.session else "—"
        self.query_one("#ws-status", Static).update(f"{label}  ·  {text}")

    # ── login / onboarding ─────────────────────────────────────────────
    def action_switch_workspace(self) -> None:
        self.open_login()

    def open_login(self) -> None:
        self.app.push_screen(
            LoginScreen(self.profiles, can_cancel=self.session is not None),
            self._on_login_result,
        )

    def _on_login_result(self, result: ConnectResult | None) -> None:
        if result is None:
            if self.session is None:
                self._set_status("not connected · press w to sign in")
            return
        if result.save and result.host:
            self._persist_profile(result)
        self.load(WorkspaceSession(result.gateway, result.label))

    @work(group="persist")
    async def _persist_profile(self, result: ConnectResult) -> None:
        try:
            await asyncio.to_thread(
                auth.save_profile, result.save_name, result.host, result.account_id
            )
            self.profiles = await asyncio.to_thread(discover_workspaces)
            self.notify(f"Saved profile “{result.save_name}”.")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Could not save profile: {exc}", severity="error")

    # ── connect + warm cache (US-2, US-14) ──────────────────────────────
    def load(self, session: WorkspaceSession) -> None:
        self.session = session
        self._warm()

    @work(exclusive=True, group="connect")
    async def _warm(self) -> None:
        session = self.session
        self.current_scope = self.current_secret = self._revealed = None
        self.scopes_pane.show([])
        self.secrets_pane.clear()
        self.detail_pane.clear()
        self._set_status("connecting…")

        identity = await asyncio.to_thread(session.authenticate)
        if not identity.authenticated:
            self._set_status(f"[$error]auth failed[/] · {identity.error}")
            return
        self._set_status(f"{identity.user_name} · loading scopes…")

        try:
            scopes = await asyncio.to_thread(session.load_scopes)
        except GatewayError as exc:
            self._set_status(f"[$error]error[/] · {exc}")
            return
        self.scopes_pane.show(scopes)

        total = len(scopes)
        for i, scope in enumerate(scopes, 1):
            await asyncio.to_thread(session.warm_scope, scope.name)
            self._set_status(f"{identity.user_name} · warming cache {i}/{total}")
            if scope.name == self.current_scope:
                self._show_scope(scope.name)
        self._set_status(f"{identity.user_name} · {total} scopes ready")

    # ── selection → render ──────────────────────────────────────────────
    def _show_scope(self, name: str) -> None:
        self.current_scope = name
        self.current_secret = None
        self._revealed = None
        secrets = self.session.secrets_for(name)
        self.secrets_pane.show(name, secrets)
        scope = self.session.scope(name)
        if scope:
            self.detail_pane.show_scope(scope, len(secrets), self.session.acls_for(name))

    def _show_secret(self, key: str) -> None:
        self.current_secret = key
        self._revealed = None
        self._render_secret()

    def _render_secret(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            return
        scope, key = self.current_scope, self.current_secret
        value = (
            self.session.cached_value(scope, key)
            if self._revealed == (scope, key)
            else None
        )
        self.detail_pane.show_secret(self.session.secret(scope, key), scope, key, value)

    @on(ScopesPane.Selected)
    def _on_scope_selected(self, message: ScopesPane.Selected) -> None:
        if self.session:
            self._show_scope(message.scope)

    @on(SecretsPane.Selected)
    def _on_secret_selected(self, message: SecretsPane.Selected) -> None:
        self._show_secret(message.key)

    @on(ListView.Selected, "#scopes-list")
    def _scope_activated(self) -> None:
        self.secrets_pane.focus_table()

    # ── keyboard navigation ─────────────────────────────────────────────
    _PANES = ("scopes-list", "secrets-table")

    def action_vi(self, direction: str) -> None:
        fn = getattr(self.focused, f"action_cursor_{direction}", None)
        if fn:
            fn()

    def action_focus_pane(self, direction: str) -> None:
        current = getattr(self.focused, "id", None)
        idx = self._PANES.index(current) if current in self._PANES else 0
        step = 1 if direction == "right" else -1
        target = self._PANES[(idx + step) % len(self._PANES)]
        self.query_one(f"#{target}").focus()

    def action_jump(self, where: str) -> None:
        widget = self.focused
        if isinstance(widget, ListView) and len(widget):
            widget.index = 0 if where == "top" else len(widget) - 1
        elif isinstance(widget, DataTable) and widget.row_count:
            row = 0 if where == "top" else widget.row_count - 1
            widget.move_cursor(row=row)

    # ── command palette ─────────────────────────────────────────────────
    def command_catalog(self) -> list[tuple[str, object]]:
        return [
            ("New secret", self.action_new_secret),
            ("New scope", self.action_new_scope),
            ("Edit secret value", self.action_edit_secret),
            ("Delete selected", self.action_delete),
            ("Manage scope permissions", self.action_permissions),
            ("Reveal secret value", self.action_reveal),
            ("Copy secret value", self.action_copy),
            ("Refresh scope", self.action_refresh_scope),
            ("Refresh workspace", self.action_refresh_workspace),
            ("Authorization overview", self.action_auth),
            ("Switch / add workspace", self.action_switch_workspace),
            ("Help", self.action_help),
        ]

    # ── generic actions ─────────────────────────────────────────────────
    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_auth(self) -> None:
        if self.session:
            self.app.push_screen(
                AuthScreen(self.session.identity, self.session.auth_summary())
            )

    def action_permissions(self) -> None:
        if not (self.session and self.current_scope):
            self.notify("Select a scope first.")
            return
        scope = self.current_scope
        self.app.push_screen(
            PermissionsScreen(self.session, scope),
            lambda _: self._show_scope(scope),  # re-render ACLs after editing
        )

    # ── create / edit / delete ──────────────────────────────────────────
    def action_new_scope(self) -> None:
        if self.session:
            self.app.push_screen(ScopeFormModal(), self._on_new_scope)

    def _on_new_scope(self, name: str | None) -> None:
        if name:
            self._create_scope(name)

    @work(group="mutate")
    async def _create_scope(self, name: str) -> None:
        try:
            await asyncio.to_thread(self.session.create_scope, name)
        except GatewayError as exc:
            self.notify(f"Create scope failed: {exc}", severity="error")
            return
        self.scopes_pane.show(self.session.scopes)
        self.notify(f"Scope “{name}” created.")

    def action_new_secret(self) -> None:
        if not (self.session and self.current_scope):
            self.notify("Select a scope first.")
            return
        self.app.push_screen(SecretFormModal(self.current_scope), self._on_secret_form)

    def action_edit_secret(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            self.notify("Select a secret first.")
            return
        self.app.push_screen(
            SecretFormModal(self.current_scope, key=self.current_secret, edit=True),
            self._on_secret_form,
        )

    def _on_secret_form(self, result: tuple[str, str] | None) -> None:
        if result:
            key, value = result
            self._put_secret(self.current_scope, key, value)

    @work(group="mutate")
    async def _put_secret(self, scope: str, key: str, value: str) -> None:
        try:
            await asyncio.to_thread(self.session.put_secret, scope, key, value)
        except GatewayError as exc:
            self.notify(f"Save failed: {exc}", severity="error")
            return
        if scope == self.current_scope:
            self._show_scope(scope)
        self.notify(f"Secret “{key}” saved.")

    def action_delete(self) -> None:
        focused_id = getattr(self.focused, "id", None)
        if focused_id == "secrets-table" and self.current_secret:
            key = self.current_secret
            self.app.push_screen(
                ConfirmModal("Delete secret", f"Delete secret “{key}”?"),
                lambda ok: self._delete_secret(self.current_scope, key) if ok else None,
            )
        elif focused_id == "scopes-list" and self.current_scope:
            name = self.current_scope
            self.app.push_screen(
                ConfirmModal(
                    "Delete scope", f"Delete scope “{name}” and all its secrets?"
                ),
                lambda ok: self._delete_scope(name) if ok else None,
            )
        else:
            self.notify("Nothing selected to delete.")

    @work(group="mutate")
    async def _delete_secret(self, scope: str, key: str) -> None:
        try:
            await asyncio.to_thread(self.session.delete_secret, scope, key)
        except GatewayError as exc:
            self.notify(f"Delete failed: {exc}", severity="error")
            return
        if scope == self.current_scope:
            self._show_scope(scope)
        self.notify(f"Secret “{key}” deleted.")

    @work(group="mutate")
    async def _delete_scope(self, name: str) -> None:
        try:
            await asyncio.to_thread(self.session.delete_scope, name)
        except GatewayError as exc:
            self.notify(f"Delete failed: {exc}", severity="error")
            return
        self.scopes_pane.show(self.session.scopes)
        self.secrets_pane.clear()
        self.notify(f"Scope “{name}” deleted.")

    # ── reveal / copy (US-10, US-16) ────────────────────────────────────
    def action_reveal(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            return
        target = (self.current_scope, self.current_secret)
        if self._revealed == target:
            self._revealed = None
            self._render_secret()
        elif self.session.cached_value(*target) is not None:
            self._revealed = target
            self._render_secret()
        else:
            self._reveal_fetch(target)

    @work(group="reveal")
    async def _reveal_fetch(self, target: tuple[str, str]) -> None:
        try:
            await asyncio.to_thread(self.session.reveal, *target)
        except GatewayError as exc:
            self.notify(f"Cannot read value: {exc}", severity="error")
            return
        if (self.current_scope, self.current_secret) == target:
            self._revealed = target
            self._render_secret()

    def action_copy(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            return
        target = (self.current_scope, self.current_secret)
        cached = self.session.cached_value(*target)
        if cached is not None:
            self.app.copy_to_clipboard(cached)
            self.notify(f"Copied “{target[1]}” to clipboard.")
        else:
            self._copy_fetch(target)

    @work(group="reveal")
    async def _copy_fetch(self, target: tuple[str, str]) -> None:
        try:
            value = await asyncio.to_thread(self.session.reveal, *target)
        except GatewayError as exc:
            self.notify(f"Cannot read value: {exc}", severity="error")
            return
        self.app.copy_to_clipboard(value)
        self.notify(f"Copied “{target[1]}” to clipboard.")

    # ── refresh (US-15) ─────────────────────────────────────────────────
    def action_refresh_scope(self) -> None:
        if self.session and self.current_scope:
            self._refresh_scope(self.current_scope)

    @work(group="refresh")
    async def _refresh_scope(self, name: str) -> None:
        self._set_status(f"refreshing {name}…")
        await asyncio.to_thread(self.session.refresh_scope, name)
        if name == self.current_scope:
            self._show_scope(name)
        self._set_status(f"{self.session.identity.user_name} · refreshed {name}")

    def action_refresh_workspace(self) -> None:
        if self.session:
            self._warm()
