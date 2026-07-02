"""MainScreen — the three-pane secret browser for one workspace session.

Holds no business logic: every operation is delegated to a `WorkspaceService`
(run in a worker thread), and rendering is delegated to the pane widgets. The
screen's job is wiring — selections in, session calls out, results to panes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from pathlib import Path

from rich.markup import escape
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Input, Static

from ...application import (
    OnboardingService,
    WorkspaceService,
    format_dotenv,
    parse_dotenv,
)
from ...domain import AuthError, Settings, StoreError
from ..modals import (
    AuditScreen,
    AuthScreen,
    ConfirmModal,
    HelpScreen,
    MoveSecretModal,
    PathModal,
    PermissionsScreen,
    PrincipalModal,
    ScopeFormModal,
    SearchModal,
    SecretFormModal,
    SnippetModal,
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
        Binding("m", "move_secret", "Move/copy", show=False),
        Binding("d", "delete", "Delete"),
        Binding("p", "permissions", "Perms"),
        Binding("space", "reveal", "Reveal"),
        Binding("c", "copy", "Copy"),
        Binding("C", "copy_snippet", "Copy ref", show=False),
        Binding("ctrl+f", "search", "Search", show=False),
        Binding("u", "undo_delete", "Undo delete", show=False),
        Binding("r", "refresh_scope", "Refresh", show=False),
        Binding("R", "refresh_workspace", "Refresh all", show=False),
        Binding("a", "auth", "Auth", show=False),
        Binding("A", "audit", "Audit", show=False),
        Binding("s", "sort", "Sort", show=False),
        Binding("S", "sort_reverse", "Sort reverse", show=False),
        Binding("slash", "filter", "Filter"),
        Binding("f", "toggle_scopes", "Mine/all", show=False),
        Binding("question_mark", "help", "Help"),
        Binding("q", "app.quit", "Quit", show=False),
        Binding("escape", "cancel_filter", "Clear filter", show=False),
        # navigation — vim + arrows, fully keyboard driven
        Binding("tab,right,l", "focus_pane('right')", "Pane →", show=False),
        Binding("shift+tab,left,h", "focus_pane('left')", "Pane ←", show=False),
        Binding("j,down", "vi('down')", "Down", show=False),
        Binding("k,up", "vi('up')", "Up", show=False),
        Binding("g", "jump('top')", "Top", show=False),
        Binding("G", "jump('bottom')", "Bottom", show=False),
    ]

    # a revealed value hides itself after this many seconds (shoulder-surfing
    # guard); class-level so tests can shrink it
    REVEAL_TIMEOUT: float = 30.0

    def __init__(
        self,
        onboarding: OnboardingService,
        session: WorkspaceService | None = None,
        read_only: bool = False,
        settings: Settings | None = None,
        save_settings: Callable[[], None] | None = None,
        auto_connect: str | None = None,
    ) -> None:
        super().__init__()
        self._onboarding = onboarding
        self.workspaces = onboarding.available_workspaces()
        self.session = session
        self.read_only = read_only
        self._settings = settings or Settings()
        self._save_settings = save_settings or (lambda: None)
        self._auto_connect_to = auto_connect
        self.current_scope: str | None = None
        self.current_secret: str | None = None
        self._revealed: tuple[str, str] | None = None
        self._hide_timer: Timer | None = None  # pending auto-hide
        self._undo_secret: tuple[str, str, str] | None = None  # last deleted
        self._status_text: str = ""
        self._filter_target: str | None = None  # "scopes" | "secrets" while filtering
        # scope list shows only scopes the user can access; f toggles to show all
        self.show_all_scopes: bool = self._settings.show_all_scopes

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
        elif self._auto_connect_to:
            self._auto_connect(self._auto_connect_to)
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
        ro = "  ·  [$warning]read-only[/]" if self.read_only else ""
        widget.update(f"[$text-muted]{user}  ·  {self._sess.label}[/]{ro}")

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
        # filter the focused pane; from the detail pane, the secrets you
        # drilled into are the nearest list — filter those.
        focused = getattr(self.focused, "id", None)
        self._filter_target = "scopes" if focused == "scopes-table" else "secrets"
        bar = self.query_one("#filter-bar", Input)
        bar.placeholder = f"filter {self._filter_target}… (esc to clear)"
        bar.value = self._target_pane().filter_text  # reopen = refine, not restart
        bar.display = True
        bar.focus()

    def _target_pane(self) -> ScopesPane | SecretsPane:
        return self.secrets_pane if self._filter_target == "secrets" else self.scopes_pane

    def action_cancel_filter(self) -> None:
        if self.query_one("#filter-bar", Input).display:
            self._close_filter(clear=True)
            return
        # esc on a filtered pane clears its pinned filter
        fid = getattr(self.focused, "id", None)
        if fid == "scopes-table" and self.scopes_pane.filter_text:
            self.scopes_pane.apply_filter("")
        elif fid == "secrets-table" and self.secrets_pane.filter_text:
            self.secrets_pane.apply_filter("")

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
        self._settings.show_all_scopes = self.show_all_scopes
        self._save_settings()
        self._render_scopes(keep=self.current_scope, focus=False)
        if self.show_all_scopes:
            self.notify(f"Showing all {len(self._sess.scopes)} scopes.")
        else:
            self.notify("Showing only scopes you can access.")

    # ── login / onboarding ─────────────────────────────────────────────
    def action_switch_workspace(self) -> None:
        self.open_login()

    @work(group="connect")
    async def _auto_connect(self, name: str) -> None:
        """Connect straight to a discovered workspace (--profile), skipping the
        picker; any failure lands on the login screen with the reason shown."""
        ws = next((w for w in self.workspaces if w.name == name), None)
        if ws is None:
            self.notify(f"No workspace “{name}” found.", severity="error")
            self.open_login()
            return
        self._set_status(f"Connecting to {escape(ws.name)}…")
        try:
            connection = await asyncio.to_thread(self._onboarding.connect, ws)
        except AuthError as exc:
            self._set_status(
                f"Connection to {escape(ws.name)} failed — {escape(str(exc))}",
                color="$error",
            )
            self.open_login()
            return
        self.load(connection.service)

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
        self.scopes_pane.show([], reset_filter=True)
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
        self.scopes_pane.show(self._scope_rows(show_all=True), reset_filter=True)

        # warm scopes concurrently (bounded, so big workspaces load in seconds
        # without hammering the API); each scope is written under its own key,
        # so the cache writes don't race.
        total = len(scopes)
        gate = asyncio.Semaphore(8)
        done = 0

        async def warm(scope_name: str) -> None:
            nonlocal done
            async with gate:
                await asyncio.to_thread(session.warm_scope, scope_name)
            done += 1
            self._set_status(f"Loading… {done}/{total}")
            if scope_name == self.current_scope:
                self._show_scope(scope_name)

        await asyncio.gather(*(warm(s.name) for s in scopes))

        # refresh rows now that counts + access are warmed (applies the filter)
        self._render_scopes(keep=self.current_scope, focus=False)
        self._render_status()

    # ── selection → render ──────────────────────────────────────────────
    def _show_scope(self, name: str) -> None:
        self.current_scope = name
        self.current_secret = None
        self._revealed = None
        secrets = self._sess.secrets_for(name)
        scope = self._sess.scope(name)
        self.secrets_pane.show(name, secrets, keyvault=bool(scope and scope.is_keyvault))
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

    @on(DataTable.RowSelected, "#secrets-table")
    def _secret_activated(self) -> None:
        self.action_reveal()

    # ── keyboard navigation ─────────────────────────────────────────────
    _PANES = ("scopes-table", "secrets-table", "detail-scroll")

    def action_vi(self, direction: str) -> None:
        focused = self.focused
        if getattr(focused, "id", None) == "filter-bar":
            # while typing a filter, ↑/↓ drive the table being filtered
            table = self.query_one(f"#{self._filter_target}-table", DataTable)
            focused = table
        fn = getattr(focused, f"action_cursor_{direction}", None) or getattr(
            focused, f"action_scroll_{direction}", None
        )
        if fn:
            fn()

    def action_focus_pane(self, direction: str) -> None:
        current = getattr(self.focused, "id", None)
        idx = self._PANES.index(current) if current in self._PANES else 0
        step = 1 if direction == "right" else -1
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
        elif isinstance(widget, VerticalScroll):
            widget.scroll_home() if where == "top" else widget.scroll_end()

    def action_sort(self) -> None:
        pane = self._sortable_pane()
        if pane:
            pane.cycle_sort()

    def action_sort_reverse(self) -> None:
        pane = self._sortable_pane()
        if pane:
            pane.flip_sort()

    def _sortable_pane(self) -> ScopesPane | SecretsPane | DetailPane | None:
        fid = getattr(self.focused, "id", None)
        if fid == "secrets-table":
            return self.secrets_pane
        if fid == "scopes-table":
            return self.scopes_pane
        if fid == "detail-scroll":
            return self.detail_pane
        return None

    def _blocked_read_only(self) -> bool:
        """Guard for mutating actions reached via the command palette."""
        if self.read_only:
            self.notify("Read-only mode — changes are disabled.")
        return self.read_only

    def _scope_is_keyvault(self, name: str | None = None) -> bool:
        """Azure Key Vault-backed scopes are read-only through the secrets API."""
        name = name or self.current_scope
        if not (self.session and name):
            return False
        scope = self._sess.scope(name)
        return bool(scope and scope.is_keyvault)

    def _notify_keyvault(self) -> None:
        self.notify(
            f"“{self.current_scope}” is Key Vault-backed — manage its secrets in Azure."
        )

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Context-aware footer — gate actions on the current *selection*, not the
        focused pane, so the footer stays correct whichever of the three panes has
        focus. In Textual, returning False hides AND disables the binding."""
        mutating = (
            "new_secret",
            "new_scope",
            "edit_secret",
            "move_secret",
            "delete",
            "undo_delete",
            "import_env",
        )
        if self.read_only and action in mutating:
            return False
        if action in ("reveal", "copy", "copy_snippet"):
            return self.current_secret is not None
        if action == "move_secret":
            return self.current_secret is not None
        if action == "edit_secret":
            return self.current_secret is not None and not self._scope_is_keyvault()
        if action == "new_secret":
            return self.current_scope is not None and not self._scope_is_keyvault()
        if action in ("permissions", "delete"):
            return self.current_scope is not None
        return True

    # ── command palette ─────────────────────────────────────────────────
    def command_catalog(self) -> list[tuple[str, object]]:
        return [
            ("Search all scopes", self.action_search),
            ("New secret", self.action_new_secret),
            ("New scope", self.action_new_scope),
            ("Edit secret value", self.action_edit_secret),
            ("Move / copy secret", self.action_move_secret),
            ("Delete selected", self.action_delete),
            ("Undo last secret delete", self.action_undo_delete),
            ("Manage scope permissions", self.action_permissions),
            ("Who has access (principal lookup)", self.action_principal_lookup),
            ("Import .env file into scope", self.action_import_env),
            ("Copy scope as .env (keys only)", self.action_export_env_keys),
            ("Copy scope as .env (with values)", self.action_export_env_values),
            ("Reveal secret value", self.action_reveal),
            ("Copy secret value", self.action_copy),
            ("Copy code reference (dbutils / CLI)", self.action_copy_snippet),
            ("Forget revealed values", self.action_forget_values),
            ("Sort: next column", self.action_sort),
            ("Sort: reverse direction", self.action_sort_reverse),
            ("Refresh scope", self.action_refresh_scope),
            ("Refresh workspace", self.action_refresh_workspace),
            ("Authorization overview", self.action_auth),
            ("Audit: stale secrets", self.action_audit),
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
            PermissionsScreen(self._sess, scope, read_only=self.read_only),
            lambda _: self._show_scope(scope),  # re-render ACLs after editing
        )

    # ── create / edit / delete ──────────────────────────────────────────
    def action_new_scope(self) -> None:
        if self.session and not self._blocked_read_only():
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
        if self._blocked_read_only():
            return
        if self._scope_is_keyvault():
            self._notify_keyvault()
            return
        self.app.push_screen(SecretFormModal(self.current_scope), self._on_secret_form)

    def action_edit_secret(self) -> None:
        if not (self.session and self.current_scope and self.current_secret):
            self.notify("Select a secret first.")
            return
        if self._blocked_read_only():
            return
        if self._scope_is_keyvault():
            self._notify_keyvault()
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

    def action_move_secret(self) -> None:
        """Move, rename, duplicate, or copy the selected secret."""
        if not (self.session and self.current_scope and self.current_secret):
            self.notify("Select a secret first.")
            return
        if self._blocked_read_only():
            return
        targets = [s.name for s in self._sess.scopes if not s.is_keyvault]
        if not targets:
            self.notify("No writable scope to copy into.")
            return
        self.app.push_screen(
            MoveSecretModal(
                targets,
                self.current_scope,
                self.current_secret,
                source_locked=self._scope_is_keyvault(),
            ),
            partial(self._on_move_secret, self.current_scope, self.current_secret),
        )

    def _on_move_secret(
        self, scope: str, key: str, result: tuple[str, str, bool] | None
    ) -> None:
        if result:
            to_scope, to_key, keep = result
            self._move_secret(scope, key, to_scope, to_key, keep)

    @work(group="mutate")
    async def _move_secret(
        self, scope: str, key: str, to_scope: str, to_key: str, keep: bool
    ) -> None:
        try:
            value = await asyncio.to_thread(self._sess.reveal, scope, key)
            await asyncio.to_thread(self._sess.put_secret, to_scope, to_key, value)
            if not keep:
                await asyncio.to_thread(self._sess.delete_secret, scope, key)
        except StoreError as exc:
            self.notify(f"Move failed: {exc}", severity="error")
            return
        if not keep:
            self._undo_secret = (scope, key, value)
        if self.current_scope in (scope, to_scope):
            self._show_scope(self.current_scope)
            self.secrets_pane.select(to_key if self.current_scope == to_scope else key)
        self._render_scopes(keep=self.current_scope, focus=False)
        verb = "Copied" if keep else "Moved"
        self.notify(f"{verb} “{key}” → {to_scope}/{to_key}.")

    def action_delete(self) -> None:
        """Delete what's selected: the scope from the scopes pane; the secret from
        the secrets/detail panes (falling back to the scope when it has none)."""
        if self._blocked_read_only():
            return
        focused_id = getattr(self.focused, "id", None)
        target_secret = focused_id != "scopes-table" and self.current_secret
        if target_secret and self.current_scope and self.current_secret:
            if self._scope_is_keyvault():
                self._notify_keyvault()
                return
            scope, key = self.current_scope, self.current_secret
            self.app.push_screen(
                ConfirmModal(
                    "Delete secret",
                    f"Permanently delete [b]{key}[/] from [b]{scope}[/].\n"
                    "[$text-muted]This can't be undone.[/]",
                ),
                partial(self._delete_secret_if, scope, key),
            )
        elif self.current_scope:
            name = self.current_scope
            count = len(self._sess.secrets_for(name))
            tail = (
                f"and its {count} secret{'s' if count != 1 else ''}"
                if count
                else "(it has no secrets)"
            )
            self.app.push_screen(
                ConfirmModal(
                    "Delete scope",
                    f"Permanently delete [b]{name}[/] {tail}.\n"
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
        try:  # grab the value first so the delete is undoable
            value: str | None = await asyncio.to_thread(self._sess.reveal, scope, key)
        except StoreError:
            value = None
        try:
            await asyncio.to_thread(self._sess.delete_secret, scope, key)
        except StoreError as exc:
            self.notify(f"Delete failed: {exc}", severity="error")
            return
        if scope == self.current_scope:
            self._show_scope(scope)
        self._render_scopes(keep=self.current_scope, focus=False)
        if value is not None:
            self._undo_secret = (scope, key, value)
            self.notify(f"Secret “{key}” deleted — press u to undo.")
        else:
            self.notify(f"Secret “{key}” deleted.")

    def action_undo_delete(self) -> None:
        """Restore the most recently deleted secret."""
        if not (self.session and self._undo_secret) or self._blocked_read_only():
            return
        scope, key, value = self._undo_secret
        self._undo_secret = None
        if self._sess.scope(scope) is None:
            self.notify(f"Cannot undo — scope “{scope}” is gone.", severity="error")
            return
        self._put_secret(scope, key, value)

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
            self._hide_value()
        elif self._sess.cached_value(*target) is not None:
            self._show_value(target)
        else:
            self._reveal_fetch(target)

    def _show_value(self, target: tuple[str, str]) -> None:
        self._revealed = target
        self._render_secret()
        # shoulder-surfing guard: the value hides itself after a short while
        if self._hide_timer:
            self._hide_timer.stop()
        self._hide_timer = self.set_timer(self.REVEAL_TIMEOUT, self._hide_value)

    def _hide_value(self) -> None:
        if self._hide_timer:
            self._hide_timer.stop()
            self._hide_timer = None
        if self._revealed:
            self._revealed = None
            self._render_secret()

    @work(group="reveal")
    async def _reveal_fetch(self, target: tuple[str, str]) -> None:
        scope, key = target
        try:
            await asyncio.to_thread(self._sess.reveal, scope, key)
        except StoreError as exc:
            self.notify(f"Cannot read value: {exc}", severity="error")
            return
        if (self.current_scope, self.current_secret) == target:
            self._show_value(target)

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

    def action_copy_snippet(self) -> None:
        """Copy a code reference to the secret (what goes in notebooks/jobs)."""
        if not (self.session and self.current_scope and self.current_secret):
            return
        self.app.push_screen(
            SnippetModal(self.current_scope, self.current_secret), self._on_snippet
        )

    def _on_snippet(self, snippet: str | None) -> None:
        if snippet:
            self.app.copy_to_clipboard(snippet)
            self.notify("Reference copied to clipboard.")

    def action_forget_values(self) -> None:
        """Purge every cached secret value (and any pending undo) from memory."""
        if self.session is None:
            return
        self._sess.forget_values()
        self._undo_secret = None
        self._hide_value()
        self.notify("Forgot all revealed values.")

    # ── .env import / export ────────────────────────────────────────────
    def action_import_env(self) -> None:
        """Bulk-load KEY=VALUE pairs from a .env file into the selected scope."""
        if not (self.session and self.current_scope):
            self.notify("Select a scope first.")
            return
        if self._blocked_read_only():
            return
        if self._scope_is_keyvault():
            self._notify_keyvault()
            return
        self.app.push_screen(
            PathModal("Import .env", "path to a .env file (~/project/.env)"),
            self._on_import_path,
        )

    def _on_import_path(self, path_str: str | None) -> None:
        if not (path_str and self.current_scope):
            return
        try:
            text = Path(path_str).expanduser().read_text()
        except OSError as exc:
            self.notify(f"Cannot read file: {exc}", severity="error")
            return
        entries = parse_dotenv(text)
        if not entries:
            self.notify("No KEY=VALUE entries found in that file.")
            return
        scope = self.current_scope
        existing = {s.key for s in self._sess.secrets_for(scope)}
        overwrite = len(entries.keys() & existing)
        count = len(entries)
        plural = "s" if count != 1 else ""
        message = f"Import [b]{count}[/] secret{plural} into [b]{scope}[/]."
        if overwrite:
            message += (
                f"\n[$warning]{overwrite} existing "
                f"key{'s' if overwrite != 1 else ''} will be overwritten.[/]"
            )
        self.app.push_screen(
            ConfirmModal(
                "Import .env", message, danger=bool(overwrite), ok_label="Import"
            ),
            partial(self._import_env_if, scope, entries),
        )

    def _import_env_if(
        self, scope: str, entries: dict[str, str], confirmed: bool | None
    ) -> None:
        if confirmed:
            self._import_env(scope, entries)

    @work(group="mutate")
    async def _import_env(self, scope: str, entries: dict[str, str]) -> None:
        done = 0
        try:
            for key, value in entries.items():
                await asyncio.to_thread(self._sess.put_secret, scope, key, value)
                done += 1
        except StoreError as exc:
            self.notify(
                f"Import stopped after {done}/{len(entries)}: {exc}", severity="error"
            )
        else:
            self.notify(f"Imported {done} secrets into “{scope}”.")
        if scope == self.current_scope:
            self._show_scope(scope)
        self._render_scopes(keep=self.current_scope, focus=False)

    def action_export_env_keys(self) -> None:
        """Copy the scope's keys as a .env template (no values)."""
        if not (self.session and self.current_scope):
            self.notify("Select a scope first.")
            return
        secrets = self._sess.secrets_for(self.current_scope)
        if not secrets:
            self.notify("The scope has no secrets.")
            return
        self.app.copy_to_clipboard(
            format_dotenv([(s.key, "") for s in secrets], redact=True)
        )
        self.notify(f"Copied {len(secrets)} keys as a .env template.")

    def action_export_env_values(self) -> None:
        """Copy the scope as .env WITH values — clipboard only, behind a confirm."""
        if not (self.session and self.current_scope):
            self.notify("Select a scope first.")
            return
        scope = self.current_scope
        count = len(self._sess.secrets_for(scope))
        if not count:
            self.notify("The scope has no secrets.")
            return
        self.app.push_screen(
            ConfirmModal(
                "Export values",
                f"Copy all [b]{count}[/] values in [b]{scope}[/] to the clipboard.\n"
                "[$text-muted]Nothing touches disk, but the clipboard is readable "
                "by other apps.[/]",
                ok_label="Copy",
            ),
            partial(self._export_values_if, scope),
        )

    def _export_values_if(self, scope: str, confirmed: bool | None) -> None:
        if confirmed:
            self._export_values(scope)

    @work(group="reveal")
    async def _export_values(self, scope: str) -> None:
        pairs: list[tuple[str, str]] = []
        for s in self._sess.secrets_for(scope):
            try:
                value = await asyncio.to_thread(self._sess.reveal, scope, s.key)
            except StoreError as exc:
                self.notify(f"Cannot read “{s.key}”: {exc}", severity="error")
                return
            pairs.append((s.key, value))
        self.app.copy_to_clipboard(format_dotenv(pairs))
        self.notify(f"Copied {len(pairs)} entries with values (clipboard only).")

    # ── global search + audit + principal lookup ───────────────────────
    def action_search(self) -> None:
        if self.session is None:
            return
        entries = [(s.scope, s.key) for s in self._sess.all_secrets()]
        self.app.push_screen(SearchModal(entries), self._on_search)

    def action_audit(self) -> None:
        """Stale-secret audit over the warmed metadata (enter jumps there)."""
        if self.session is None:
            return
        screen = AuditScreen(
            self._sess.all_secrets(), threshold=self._settings.audit_threshold
        )
        self.app.push_screen(screen, partial(self._after_audit, screen))

    def _after_audit(self, screen: AuditScreen, result: tuple[str, str] | None) -> None:
        if screen.threshold != self._settings.audit_threshold:
            self._settings.audit_threshold = screen.threshold
            self._save_settings()
        self._on_search(result)

    def action_principal_lookup(self) -> None:
        """Who has access to what — search principals across every scope's ACLs."""
        if self.session is None:
            return
        entries = [
            (acl.principal, scope, acl.permission)
            for scope, acl in self._sess.acl_entries()
        ]
        self.app.push_screen(PrincipalModal(entries), self._on_principal)

    def _on_principal(self, scope: str | None) -> None:
        if not scope:
            return
        self._show_scope(scope)
        self.scopes_pane.select(scope)
        self.scopes_pane.focus_table()

    def _on_search(self, result: tuple[str, str] | None) -> None:
        if not result:
            return
        scope, key = result
        self._show_scope(scope)
        self.scopes_pane.select(scope)
        self.secrets_pane.select(key)
        self.secrets_pane.focus_table()

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
