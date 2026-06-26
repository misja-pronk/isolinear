"""MainScreen — the three-pane secret browser for one workspace session.

Holds no business logic: every operation is delegated to a `WorkspaceService`
(run in a worker thread), and rendering is delegated to the pane widgets. The
screen's job is wiring — selections in, session calls out, results to panes.
"""

from __future__ import annotations

import asyncio
from functools import partial

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Input, ListView, Static

from ...application import OnboardingService, WorkspaceService
from ...domain import StoreError
from ..modals import (
    AuthScreen,
    ConfirmModal,
    HelpScreen,
    PermissionsScreen,
    ScopeFormModal,
    SecretFormModal,
)
from ..widgets import DetailPane, ScopeRow, ScopesPane, SecretsPane
from .login import ConnectResult, LoginScreen


class KeystoneCommands(Provider):
    """Feeds every action into the command palette (ctrl+p)."""

    async def discover(self) -> Hits:
        """Shown as soon as the palette opens, before anything is typed."""
        screen = self.screen
        if not isinstance(screen, MainScreen):
            return
        for label, action in screen.command_catalog():
            yield DiscoveryHit(label, action, help=label)

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
    COMMANDS = {KeystoneCommands}

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
        Binding("slash", "filter", "Filter"),
        Binding("question_mark", "help", "Help"),
        Binding("escape", "cancel_filter", "Clear filter", show=False),
        # navigation — vim + arrows, fully keyboard driven
        Binding("tab,right,l", "focus_pane('right')", "Pane →", show=False),
        Binding("shift+tab,left,h", "focus_pane('left')", "Pane ←", show=False),
        Binding("j,down", "vi('down')", "Down", show=False),
        Binding("k,up", "vi('up')", "Up", show=False),
        Binding("g", "jump('top')", "Top", show=False),
        Binding("G", "jump('bottom')", "Bottom", show=False),
    ]

    def __init__(
        self, onboarding: OnboardingService, session: WorkspaceService | None = None
    ) -> None:
        super().__init__()
        self._onboarding = onboarding
        self.profiles = onboarding.saved_workspaces()
        self.session = session
        self.current_scope: str | None = None
        self.current_secret: str | None = None
        self._revealed: tuple[str, str] | None = None
        self._status_text: str = ""
        self._status_dot: tuple[str, str] = ("●", "$success")
        self._filter_target: str | None = None  # "scopes" | "secrets" while filtering

    # ── layout ─────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        with Horizontal(id="banner"):
            yield Static("⏢ KEYSTONE", id="brand")
            yield Static("", id="breadcrumb")
            yield Static("", id="ws-status")
        with Horizontal(id="body"):
            yield ScopesPane()
            yield SecretsPane()
            yield DetailPane()
        yield Input(id="filter-bar", placeholder="filter…")
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

    @property
    def _sess(self) -> WorkspaceService:
        """The active session. Callers below only run once connected."""
        assert self.session is not None, "no active session"
        return self.session

    # status-bar identity + seal indicator
    _SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    _WARM_LINES = [
        "surveying the foundation",
        "laying the courses",
        "dressing the stone",
        "setting the keystone",
        "aligning isolinear chips",
        "powering the core",
    ]

    def _set_status(self, text: str, *, dot: str = "●", color: str = "$success") -> None:
        self._status_text = text
        self._status_dot = (dot, color)
        self._render_status()

    def _render_status(self) -> None:
        widget = self.query_one("#ws-status", Static)
        if self.session is None:
            widget.update("[$text-muted]not connected · press w to sign in[/]")
            return
        dot, color = self._status_dot
        user = self._sess.identity.user_name or "—"
        seal = (
            "[b $accent]🔓 unsealed[/]" if self._revealed else "[$text-muted]🔒 sealed[/]"
        )
        widget.update(
            f"[{color}]{dot}[/] [b]{user}[/]  ·  {self._sess.label}"
            f"  ·  {self._status_text}  ·  {seal}"
        )

    def _render_breadcrumb(self) -> None:
        bc = self.query_one("#breadcrumb", Static)
        parts: list[str] = []
        if self.current_scope:
            parts.append(f"[b $primary]{self.current_scope}[/]")
        if self.current_secret:
            parts.append(f"[$accent]{self.current_secret}[/]")
        bc.update("  [dim]▸[/]  ".join(parts))

    # ── scope view models + filtering ───────────────────────────────────
    def _scope_rows(self) -> list[ScopeRow]:
        access = {s.scope: s.effective for s in self._sess.auth_summary()}
        return [
            ScopeRow(
                name=sc.name,
                icon=sc.icon,
                count=len(self._sess.secrets_for(sc.name)),
                access=access.get(sc.name, "—"),
            )
            for sc in self._sess.scopes
        ]

    def _access_for(self, name: str) -> str:
        return next(
            (s.effective for s in self._sess.auth_summary() if s.scope == name), "—"
        )

    def action_filter(self) -> None:
        if self.session is None:
            return
        focused = getattr(self.focused, "id", None)
        self._filter_target = "secrets" if focused == "secrets-table" else "scopes"
        bar = self.query_one("#filter-bar", Input)
        bar.placeholder = f"filter {self._filter_target}… (esc to clear)"
        bar.value = ""
        bar.display = True
        bar.focus()

    def action_cancel_filter(self) -> None:
        if self.query_one("#filter-bar", Input).display:
            self._close_filter(clear=True)

    def _close_filter(self, *, clear: bool) -> None:
        if clear:
            self._apply_filter("")
        self.query_one("#filter-bar", Input).display = False
        if self._filter_target == "secrets":
            self.secrets_pane.focus_table()
        else:
            self.scopes_pane.query_one(ListView).focus()
        self._filter_target = None

    def _apply_filter(self, text: str) -> None:
        if self._filter_target == "secrets":
            self.secrets_pane.apply_filter(text)
        elif self._filter_target == "scopes":
            self.scopes_pane.apply_filter(text)

    @on(Input.Changed, "#filter-bar")
    def _filter_changed(self, event: Input.Changed) -> None:
        self._apply_filter(event.value)

    @on(Input.Submitted, "#filter-bar")
    def _filter_submitted(self) -> None:
        self._close_filter(clear=False)

    # ── login / onboarding ─────────────────────────────────────────────
    def action_switch_workspace(self) -> None:
        self.open_login()

    def open_login(self) -> None:
        self.app.push_screen(
            LoginScreen(
                self.profiles, self._onboarding, can_cancel=self.session is not None
            ),
            self._on_login_result,
        )

    def _on_login_result(self, result: ConnectResult | None) -> None:
        if result is None:
            if self.session is None:
                self._set_status("not connected · press w to sign in")
            return
        if result.save and result.connection.host:
            self._persist_profile(result)
        self.load(result.connection.service)

    @work(group="persist")
    async def _persist_profile(self, result: ConnectResult) -> None:
        conn = result.connection
        try:
            await asyncio.to_thread(
                self._onboarding.save_profile,
                result.save_name,
                conn.host,
                conn.account_id,
            )
            self.profiles = await asyncio.to_thread(self._onboarding.saved_workspaces)
            self.notify(f"Saved profile “{result.save_name}”.")
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Could not save profile: {exc}", severity="error")

    # ── connect + warm cache (US-2, US-14) ──────────────────────────────
    def load(self, session: WorkspaceService) -> None:
        self.session = session
        self._warm()

    @work(exclusive=True, group="connect")
    async def _warm(self) -> None:
        session = self.session
        if session is None:
            return
        self.current_scope = self.current_secret = self._revealed = None
        self.scopes_pane.show([])
        self.secrets_pane.clear()
        self.detail_pane.clear()
        self._render_breadcrumb()
        self._set_status("establishing uplink…", dot="◐", color="$accent")

        identity = await asyncio.to_thread(session.authenticate)
        if not identity.authenticated:
            self._set_status(
                f"[$error]access denied[/] · {identity.error}", dot="○", color="$error"
            )
            return
        self._set_status("surveying the site…", dot="◐", color="$accent")

        try:
            scopes = await asyncio.to_thread(session.load_scopes)
        except StoreError as exc:
            self._set_status(f"[$error]{exc}[/]", dot="○", color="$error")
            return
        self.scopes_pane.show(self._scope_rows())

        total = len(scopes)
        for i, scope in enumerate(scopes, 1):
            await asyncio.to_thread(session.warm_scope, scope.name)
            spin = self._SPINNER[i % len(self._SPINNER)]
            line = self._WARM_LINES[i % len(self._WARM_LINES)]
            filled = round(i / total * 10)
            bar = f"[$primary]{'▰' * filled}[/][$panel]{'▱' * (10 - filled)}[/]"
            self._set_status(f"{line}…  {bar} {i}/{total}", dot=spin, color="$accent")
            if scope.name == self.current_scope:
                self._show_scope(scope.name)

        # refresh rows now that counts + access are warmed
        self.scopes_pane.show(self._scope_rows(), keep=self.current_scope, focus=False)
        plural = "scope" if total == 1 else "scopes"
        self._set_status(f"{total} {plural} online", dot="●", color="$success")

    # ── selection → render ──────────────────────────────────────────────
    def _show_scope(self, name: str) -> None:
        self.current_scope = name
        self.current_secret = None
        self._revealed = None
        secrets = self._sess.secrets_for(name)
        self.secrets_pane.show(name, secrets)
        scope = self._sess.scope(name)
        if scope:
            self.detail_pane.show_scope(
                scope, len(secrets), self._sess.acls_for(name), self._access_for(name)
            )
        self._render_breadcrumb()
        self._render_status()  # reset the seal indicator

    def _show_secret(self, key: str) -> None:
        self.current_secret = key
        self._revealed = None
        self._render_secret()
        self._render_breadcrumb()

    def _render_secret(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            return
        scope, key = self.current_scope, self.current_secret
        value = (
            self._sess.cached_value(scope, key)
            if self._revealed == (scope, key)
            else None
        )
        self.detail_pane.show_secret(self._sess.secret(scope, key), scope, key, value)
        self._render_status()  # flip 🔒 sealed ↔ 🔓 unsealed

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
                AuthScreen(self._sess.identity, self._sess.auth_summary())
            )

    def action_permissions(self) -> None:
        if not (self.session and self.current_scope):
            self.notify("Select a scope first.")
            return
        scope = self.current_scope
        self.app.push_screen(
            PermissionsScreen(self._sess, scope),
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
            await asyncio.to_thread(self._sess.create_scope, name)
        except StoreError as exc:
            self.notify(f"Create scope failed: {exc}", severity="error")
            return
        self.scopes_pane.show(self._scope_rows(), keep=name)
        self.notify(f"🔒 Scope “{name}” created.")

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
            await asyncio.to_thread(self._sess.put_secret, scope, key, value)
        except StoreError as exc:
            self.notify(f"Save failed: {exc}", severity="error")
            return
        if scope == self.current_scope:
            self._show_scope(scope)
        self.scopes_pane.show(self._scope_rows(), keep=self.current_scope, focus=False)
        self.notify(f"🔑 Secret “{key}” saved.")

    def action_delete(self) -> None:
        focused_id = getattr(self.focused, "id", None)
        if focused_id == "secrets-table" and self.current_scope and self.current_secret:
            scope, key = self.current_scope, self.current_secret
            self.app.push_screen(
                ConfirmModal("Delete secret", f"Delete secret “{key}”?"),
                partial(self._delete_secret_if, scope, key),
            )
        elif focused_id == "scopes-list" and self.current_scope:
            name = self.current_scope
            self.app.push_screen(
                ConfirmModal(
                    "Delete scope", f"Delete scope “{name}” and all its secrets?"
                ),
                partial(self._delete_scope_if, name),
            )
        else:
            self.notify("Nothing selected to delete.")

    def _delete_secret_if(self, scope: str, key: str, confirmed: bool | None) -> None:
        if confirmed:
            self._delete_secret(scope, key)

    def _delete_scope_if(self, name: str, confirmed: bool | None) -> None:
        if confirmed:
            self._delete_scope(name)

    @work(group="mutate")
    async def _delete_secret(self, scope: str, key: str) -> None:
        try:
            await asyncio.to_thread(self._sess.delete_secret, scope, key)
        except StoreError as exc:
            self.notify(f"Delete failed: {exc}", severity="error")
            return
        if scope == self.current_scope:
            self._show_scope(scope)
        self.scopes_pane.show(self._scope_rows(), keep=self.current_scope, focus=False)
        self.notify(f"Secret “{key}” deleted.")

    @work(group="mutate")
    async def _delete_scope(self, name: str) -> None:
        try:
            await asyncio.to_thread(self._sess.delete_scope, name)
        except StoreError as exc:
            self.notify(f"Delete failed: {exc}", severity="error")
            return
        self.current_scope = self.current_secret = None
        self.scopes_pane.show(self._scope_rows())
        self.secrets_pane.clear()
        self.detail_pane.clear()
        self._render_breadcrumb()
        self.notify(f"Scope “{name}” deleted.")

    # ── reveal / copy (US-10, US-16) ────────────────────────────────────
    def action_reveal(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            return
        target = (self.current_scope, self.current_secret)
        if self._revealed == target:
            self._revealed = None
            self._render_secret()
        elif self._sess.cached_value(*target) is not None:
            self._revealed = target
            self._render_secret()
        else:
            self._reveal_fetch(target)

    @work(group="reveal")
    async def _reveal_fetch(self, target: tuple[str, str]) -> None:
        scope, key = target
        try:
            await asyncio.to_thread(self._sess.reveal, scope, key)
        except StoreError as exc:
            self.notify(f"Cannot read value: {exc}", severity="error")
            return
        if (self.current_scope, self.current_secret) == target:
            self._revealed = target
            self._render_secret()

    def action_copy(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            return
        target = (self.current_scope, self.current_secret)
        cached = self._sess.cached_value(*target)
        if cached is not None:
            self.app.copy_to_clipboard(cached)
            self.notify(f"📋 Copied “{target[1]}” to clipboard.")
        else:
            self._copy_fetch(target)

    @work(group="reveal")
    async def _copy_fetch(self, target: tuple[str, str]) -> None:
        scope, key = target
        try:
            value = await asyncio.to_thread(self._sess.reveal, scope, key)
        except StoreError as exc:
            self.notify(f"Cannot read value: {exc}", severity="error")
            return
        self.app.copy_to_clipboard(value)
        self.notify(f"📋 Copied “{target[1]}” to clipboard.")

    # ── refresh (US-15) ─────────────────────────────────────────────────
    def action_refresh_scope(self) -> None:
        if self.session and self.current_scope:
            self._refresh_scope(self.current_scope)

    @work(group="refresh")
    async def _refresh_scope(self, name: str) -> None:
        self._set_status(f"refreshing {name}…")
        await asyncio.to_thread(self._sess.refresh_scope, name)
        if name == self.current_scope:
            self._show_scope(name)
        self.scopes_pane.show(self._scope_rows(), keep=self.current_scope, focus=False)
        self._set_status(f"{self._sess.identity.user_name} · refreshed {name}")

    def action_refresh_workspace(self) -> None:
        if self.session:
            self._warm()
