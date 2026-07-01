"""MainScreen — the three-pane secret browser for one workspace session.

Holds no business logic: every operation is delegated to a `WorkspaceService`
(run in a worker thread), and rendering is delegated to the pane widgets. The
screen's job is wiring — selections in, session calls out, results to panes.
"""

from __future__ import annotations

import asyncio
from functools import partial

from rich.markup import escape
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Input, Static

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


class IsolinearCommands(Provider):
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
    COMMANDS = {IsolinearCommands}

    BINDINGS = [
        Binding("w", "switch_workspace", "Workspace", show=False),
        Binding("n", "new_secret", "New"),
        Binding("N", "new_scope", "New scope", show=False),
        Binding("e", "edit_secret", "Edit"),
        Binding("d", "delete", "Delete"),
        Binding("p", "permissions", "Perms"),
        Binding("space", "reveal", "Reveal"),
        Binding("c", "copy", "Copy"),
        Binding("r", "refresh_scope", "Refresh", show=False),
        Binding("R", "refresh_workspace", "Refresh all", show=False),
        Binding("a", "auth", "Auth", show=False),
        Binding("s", "sort", "Sort", show=False),
        Binding("slash", "filter", "Filter"),
        Binding("f", "toggle_scopes", "Mine/all", show=False),
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
        self.workspaces = onboarding.available_workspaces()
        self.session = session
        self.current_scope: str | None = None
        self.current_secret: str | None = None
        self._revealed: tuple[str, str] | None = None
        self._status_text: str = ""
        self._filter_target: str | None = None  # "scopes" | "secrets" while filtering
        # scope list shows only scopes the user can access; f toggles to show all
        self.show_all_scopes: bool = False

    # ── layout ─────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        with Horizontal(id="banner"):
            yield Static(
                "[$scopes-color]█[/][$secrets-color]█[/][$detail-color]█[/]"
                "  [b]Isolinear[/]",
                id="brand",
            )
            yield Static("", id="breadcrumb")
            yield Static("", id="ws-status")
        with Horizontal(id="body"):
            yield ScopesPane()
            yield SecretsPane()
            yield DetailPane()
        yield Input(id="filter-bar", placeholder="filter…")
        yield Footer(show_command_palette=False)

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

    def _set_status(self, text: str, *, color: str = "$text-muted") -> None:
        self._status_text = text
        self.query_one("#ws-status", Static).update(f"[{color}]{text}[/]")

    def _render_status(self) -> None:
        widget = self.query_one("#ws-status", Static)
        if self.session is None:
            widget.update("[$text-muted]Not connected — press w to sign in[/]")
            return
        user = self._sess.identity.user_name or "—"
        widget.update(f"[$text-muted]{user}  ·  {self._sess.label}[/]")

    def _render_breadcrumb(self) -> None:
        bc = self.query_one("#breadcrumb", Static)
        parts: list[str] = []
        if self.current_scope:
            parts.append(
                f"[$text-muted]scope:[/] [$scopes-color b]{escape(self.current_scope)}[/]"
            )
        if self.current_secret:
            parts.append(
                "[$text-muted]secret:[/] "
                f"[$secrets-color b]{escape(self.current_secret)}[/]"
            )
        bc.update("   [dim]/[/]   ".join(parts))

    # ── scope view models + filtering ───────────────────────────────────
    def _scope_rows(self, *, show_all: bool = False) -> list[ScopeRow]:
        """Rows for the scopes pane. By default only scopes the user can access
        (effective permission is not "none") are included; `show_all` (and the
        `f` toggle) override that to list every scope in the workspace."""
        access = {s.scope: s.effective for s in self._sess.auth_summary()}
        keep_all = show_all or self.show_all_scopes
        return [
            ScopeRow(name=sc.name, count=len(self._sess.secrets_for(sc.name)))
            for sc in self._sess.scopes
            if keep_all or access.get(sc.name, "—") != "—"
        ]

    def _render_scopes(self, *, keep: str | None = None, focus: bool = False) -> None:
        """Repaint the scopes pane with the current filter, explaining an empty
        result that the access filter (not a missing workspace) produced."""
        rows = self._scope_rows()
        hint: str | None = None
        if not rows and not self.show_all_scopes and self._sess.scopes:
            hint = (
                "[$text-muted]No scopes you can access.\n"
                f"Press [b $primary]f[/] to show all {len(self._sess.scopes)}.[/]"
            )
        self.scopes_pane.show(rows, keep=keep, focus=focus, empty_hint=hint)

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
            self.scopes_pane.focus_table()
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

    def action_toggle_scopes(self) -> None:
        """Flip between 'only scopes I can access' and 'all scopes'."""
        if self.session is None:
            return
        self.show_all_scopes = not self.show_all_scopes
        self._render_scopes(keep=self.current_scope, focus=False)
        if self.show_all_scopes:
            self.notify(f"Showing all {len(self._sess.scopes)} scopes.")
        else:
            self.notify("Showing only scopes you can access.")

    # ── login / onboarding ─────────────────────────────────────────────
    def action_switch_workspace(self) -> None:
        self.open_login()

    def open_login(self) -> None:
        self.app.push_screen(
            LoginScreen(
                self.workspaces, self._onboarding, can_cancel=self.session is not None
            ),
            self._on_login_result,
        )

    def _on_login_result(self, result: ConnectResult | None) -> None:
        if result is None:
            if self.session is None:
                self._render_status()
            return
        if result.save and result.connection.host:
            self._persist_profile(result)
        self.load(result.connection.service)

    @work(group="persist")
    async def _persist_profile(self, result: ConnectResult) -> None:
        conn = result.connection
        try:
            await asyncio.to_thread(
                self._onboarding.save_profile, result.save_name, conn.host
            )
            self.workspaces = await asyncio.to_thread(
                self._onboarding.available_workspaces
            )
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
        self._set_status("Connecting…")

        identity = await asyncio.to_thread(session.authenticate)
        if not identity.authenticated:
            self._set_status(
                f"Access denied — {escape(identity.error or '')}", color="$error"
            )
            return
        self._set_status("Loading scopes…")

        try:
            scopes = await asyncio.to_thread(session.load_scopes)
        except StoreError as exc:
            self._set_status(escape(str(exc)), color="$error")
            return
        # during load nothing is warmed yet, so access is unknown — show every
        # scope; the list narrows to the accessible ones once warming completes.
        self.scopes_pane.show(self._scope_rows(show_all=True))

        total = len(scopes)
        for i, scope in enumerate(scopes, 1):
            await asyncio.to_thread(session.warm_scope, scope.name)
            self._set_status(f"Loading… {i}/{total}")
            if scope.name == self.current_scope:
                self._show_scope(scope.name)

        # refresh rows now that counts + access are warmed (applies the filter)
        self._render_scopes(keep=self.current_scope, focus=False)
        self._render_status()

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
        self.refresh_bindings()  # footer reflects the new selection state

    def _show_secret(self, key: str) -> None:
        self.current_secret = key
        self._revealed = None
        self._render_secret()
        self._render_breadcrumb()
        self.refresh_bindings()

    def _render_secret(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            return
        scope, key = self.current_scope, self.current_secret
        value = (
            self._sess.cached_value(scope, key)
            if self._revealed == (scope, key)
            else None
        )
        self.detail_pane.show_secret(
            self._sess.secret(scope, key),
            scope,
            key,
            value,
            self._access_for(scope),
            self._sess.acls_for(scope),
        )
        self._render_status()

    @on(ScopesPane.Selected)
    def _on_scope_selected(self, message: ScopesPane.Selected) -> None:
        # A DataTable re-emits RowHighlighted on every rebuild (refresh/sort),
        # so ignore re-selections of the current scope — otherwise a refresh
        # would reset the chosen secret and collapse a revealed value.
        if self.session and message.scope != self.current_scope:
            self._show_scope(message.scope)

    @on(SecretsPane.Selected)
    def _on_secret_selected(self, message: SecretsPane.Selected) -> None:
        if message.key != self.current_secret:
            self._show_secret(message.key)

    @on(DataTable.RowSelected, "#scopes-table")
    def _scope_activated(self) -> None:
        self.secrets_pane.focus_table()

    # ── keyboard navigation ─────────────────────────────────────────────
    _PANES = ("scopes-table", "secrets-table", "acl-table")

    def action_vi(self, direction: str) -> None:
        fn = getattr(self.focused, f"action_cursor_{direction}", None)
        if fn:
            fn()

    def action_focus_pane(self, direction: str) -> None:
        current = getattr(self.focused, "id", None)
        idx = self._PANES.index(current) if current in self._PANES else 0
        step = 1 if direction == "right" else -1
        # step to the next pane that's actually visible — the ACL table hides
        # when the selection has no permissions.
        for _ in range(len(self._PANES)):
            idx = (idx + step) % len(self._PANES)
            widget = self.query_one(f"#{self._PANES[idx]}")
            if widget.display:
                widget.focus()
                return

    @on(events.DescendantFocus)
    def _focus_changed(self) -> None:
        # keep the footer fresh as focus moves between the three panes
        self.refresh_bindings()

    def action_jump(self, where: str) -> None:
        widget = self.focused
        if isinstance(widget, DataTable) and widget.row_count:
            row = 0 if where == "top" else widget.row_count - 1
            widget.move_cursor(row=row)

    def action_sort(self) -> None:
        fid = getattr(self.focused, "id", None)
        if fid == "secrets-table":
            self.secrets_pane.cycle_sort()
        elif fid == "scopes-table":
            self.scopes_pane.cycle_sort()
        elif fid == "acl-table":
            self.detail_pane.cycle_sort()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Context-aware footer — gate actions on the current *selection*, not the
        focused pane, so the footer stays correct whichever of the three panes has
        focus. In Textual, returning False hides AND disables the binding."""
        if action in ("reveal", "copy", "edit_secret"):
            return self.current_secret is not None
        if action in ("new_secret", "permissions"):
            return self.current_scope is not None
        return True

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
            ("Sort", self.action_sort),
            ("Refresh scope", self.action_refresh_scope),
            ("Refresh workspace", self.action_refresh_workspace),
            ("Authorization overview", self.action_auth),
            ("Toggle scopes: mine / all", self.action_toggle_scopes),
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
        self._render_scopes(keep=name, focus=True)
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
            await asyncio.to_thread(self._sess.put_secret, scope, key, value)
        except StoreError as exc:
            self.notify(f"Save failed: {exc}", severity="error")
            return
        if scope == self.current_scope:
            self._show_scope(scope)
        self._render_scopes(keep=self.current_scope, focus=False)
        self.notify(f"Secret “{key}” saved.")

    def action_delete(self) -> None:
        focused_id = getattr(self.focused, "id", None)
        if focused_id == "secrets-table" and self.current_scope and self.current_secret:
            scope, key = self.current_scope, self.current_secret
            self.app.push_screen(
                ConfirmModal(
                    "Delete secret",
                    f"Permanently delete [b]{key}[/] from [b]{scope}[/].\n"
                    "[$text-muted]This can't be undone.[/]",
                ),
                partial(self._delete_secret_if, scope, key),
            )
        elif focused_id == "scopes-table" and self.current_scope:
            name = self.current_scope
            self.app.push_screen(
                ConfirmModal(
                    "Delete scope",
                    f"Permanently delete [b]{name}[/] and all its secrets.\n"
                    "[$text-muted]This can't be undone.[/]",
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
        self._render_scopes(keep=self.current_scope, focus=False)
        self.notify(f"Secret “{key}” deleted.")

    @work(group="mutate")
    async def _delete_scope(self, name: str) -> None:
        try:
            await asyncio.to_thread(self._sess.delete_scope, name)
        except StoreError as exc:
            self.notify(f"Delete failed: {exc}", severity="error")
            return
        self.current_scope = self.current_secret = None
        self._render_scopes()
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
            self.notify(f"Copied “{target[1]}” to clipboard.")
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
        self.notify(f"Copied “{target[1]}” to clipboard.")

    # ── refresh (US-15) ─────────────────────────────────────────────────
    def action_refresh_scope(self) -> None:
        if self.session and self.current_scope:
            self._refresh_scope(self.current_scope)

    @work(group="refresh")
    async def _refresh_scope(self, name: str) -> None:
        self._set_status(f"Refreshing {name}…")
        await asyncio.to_thread(self._sess.refresh_scope, name)
        if name == self.current_scope:
            self._show_scope(name)
        self._render_scopes(keep=self.current_scope, focus=False)
        self._render_status()

    def action_refresh_workspace(self) -> None:
        if self.session:
            self._warm()
