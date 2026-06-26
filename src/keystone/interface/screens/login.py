"""Login & onboarding: a takeover screen with two doors —

  1. Connect with a workspace URL  (OAuth browser login)
  2. Discover workspaces in my account  (account OAuth -> list -> pick)

plus a list of saved profiles for one-keypress reconnect. The blocking auth
calls run in worker threads; the screen narrates progress and finally dismisses
with a ConnectResult the app turns into a live session.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Select, Static

from ...application import Connection, OnboardingService
from ...domain import CLOUDS, AccountSession, AccountWorkspace, AuthError, Workspace

# An arch with its keystone (cyan) set at the crown.
LOGO = """\
[$secondary]        ▟██▙[/]
[$primary]      ▟█[/][$secondary]████[/][$primary]█▙[/]
[$primary]   ▗▟█▘[/] [$secondary]██[/] [$primary]▝█▙▖[/]
[$primary]  ▟█▀         ▀█▙[/]
[$primary]  ██           ██[/]
[$primary]  ██           ██[/]"""


@dataclass
class ConnectResult:
    connection: Connection
    save: bool = False
    save_name: str = ""


class WorkspaceUrlModal(ModalScreen[tuple[str, str] | None]):
    """Ask for a workspace URL (+ optional profile name to save)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Connect with a workspace URL", classes="dialog-title")
            yield Static(
                "[$text-muted]A browser window will open for sign-in (OAuth).[/]"
            )
            yield Input(
                placeholder="https://my-workspace.cloud.databricks.com",
                id="f-host",
            )
            yield Input(placeholder="save as profile name (optional)", id="f-save")
            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Sign in", id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#f-host", Input).focus()

    @on(Button.Pressed, "#ok")
    @on(Input.Submitted)
    def _ok(self) -> None:
        host = self.query_one("#f-host", Input).value.strip()
        if not host:
            self.query_one("#f-host", Input).focus()
            return
        self.dismiss((host, self.query_one("#f-save", Input).value.strip()))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class AccountModal(ModalScreen[tuple[str, str, str] | None]):
    """Ask for cloud + account ID (+ optional profile name to save)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Discover workspaces in my account", classes="dialog-title")
            yield Static(
                "[$text-muted]Pick your cloud and paste your Account ID "
                "(from the Databricks account console).[/]"
            )
            yield Select(
                [(c.label, c.key) for c in CLOUDS],
                prompt="Cloud",
                id="f-cloud",
                value=CLOUDS[0].key,
            )
            yield Input(placeholder="account id (UUID)", id="f-account")
            yield Input(placeholder="save as profile name (optional)", id="f-save")
            with Horizontal(classes="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Discover", id="ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#f-account", Input).focus()

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        cloud = self.query_one("#f-cloud", Select).value
        account = self.query_one("#f-account", Input).value.strip()
        if cloud is Select.BLANK or not account:
            self.query_one("#f-account", Input).focus()
            return
        save_name = self.query_one("#f-save", Input).value.strip()
        self.dismiss((str(cloud), account, save_name))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class DiscoveredPicker(ModalScreen[AccountWorkspace | None]):
    """Pick one of the workspaces discovered in the account."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, workspaces: list[AccountWorkspace]) -> None:
        super().__init__()
        self._workspaces = workspaces

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(
                f"Found {len(self._workspaces)} workspace(s)", classes="dialog-title"
            )
            yield ListView(
                *[ListItem(Label(w.label)) for w in self._workspaces],
                id="picker-list",
            )

    def on_mount(self) -> None:
        self.query_one("#picker-list", ListView).focus()

    @on(ListView.Selected)
    def _pick(self, event: ListView.Selected) -> None:
        idx = event.list_view.index or 0
        self.dismiss(self._workspaces[idx])

    def action_cancel(self) -> None:
        self.dismiss(None)


class LoginScreen(Screen[ConnectResult | None]):
    """The onboarding hub."""

    BINDINGS = [Binding("escape", "back", "Back", show=False)]

    def __init__(
        self,
        profiles: list[Workspace],
        onboarding: OnboardingService,
        can_cancel: bool = False,
    ) -> None:
        super().__init__()
        self._profiles = profiles
        self._onboarding = onboarding
        self._can_cancel = can_cancel
        self._account_session: AccountSession | None = None  # between discover -> pick

    def compose(self) -> ComposeResult:
        with Center(), Vertical(id="login-card"):
            yield Static(LOGO, id="login-logo")
            yield Static("K E Y S T O N E", id="login-wordmark")
            yield Static(
                "[$text-muted]Databricks secret manager · "
                "[i]the brick that holds the arch[/][/]",
                id="login-tagline",
            )
            if self._profiles:
                yield Static("Saved workspaces", classes="login-section")
                yield ListView(
                    *[ListItem(Label(p.label)) for p in self._profiles],
                    id="profiles",
                )
            yield Static("Or connect", classes="login-section")
            with Horizontal(id="login-actions"):
                yield Button("🔗  Workspace URL", id="btn-url", variant="primary")
                yield Button("🏢  Discover via account", id="btn-account")
                yield Button("Quit", id="btn-quit", variant="error")
            yield Static("", id="login-status")

    def on_mount(self) -> None:
        if self._profiles:
            self.query_one("#profiles", ListView).focus()
        else:
            self.query_one("#btn-url", Button).focus()

    def _status(self, text: str) -> None:
        self.query_one("#login-status", Static).update(text)

    # -- saved profiles -------------------------------------------------
    @on(ListView.Selected, "#profiles")
    def _pick_profile(self, event: ListView.Selected) -> None:
        profile = self._profiles[event.list_view.index or 0]
        connection = self._onboarding.connect_profile(profile.profile)
        self.dismiss(ConnectResult(connection=connection))

    # -- workspace URL --------------------------------------------------
    @on(Button.Pressed, "#btn-url")
    def _url(self) -> None:
        self.app.push_screen(WorkspaceUrlModal(), self._after_url_form)

    def _after_url_form(self, result: tuple[str, str] | None) -> None:
        if result:
            host, save_name = result
            self._do_url_login(host, save_name)

    @work(group="login")
    async def _do_url_login(self, host: str, save_name: str) -> None:
        self._status(f"[$accent]Opening browser to sign in to {host}…[/]")
        try:
            connection = await asyncio.to_thread(self._onboarding.connect_url, host)
        except AuthError as exc:
            self._status(f"[$error]Sign-in failed:[/] {exc}")
            return
        self.dismiss(
            ConnectResult(
                connection=connection, save=bool(save_name), save_name=save_name
            )
        )

    # -- account discovery ----------------------------------------------
    @on(Button.Pressed, "#btn-account")
    def _account(self) -> None:
        self.app.push_screen(AccountModal(), self._after_account_form)

    def _after_account_form(self, result: tuple[str, str, str] | None) -> None:
        if result:
            cloud, account_id, save_name = result
            self._do_discover(cloud, account_id, save_name)

    @work(group="login")
    async def _do_discover(self, cloud: str, account_id: str, save_name: str) -> None:
        self._status("[$accent]Opening browser to sign in to your account…[/]")
        try:
            session = await asyncio.to_thread(
                self._onboarding.discover_account, cloud, account_id
            )
        except AuthError as exc:
            self._status(f"[$error]Discovery failed:[/] {exc}")
            return
        if not session.workspaces:
            self._status("[$accent]No workspaces found in this account.[/]")
            return
        self._account_session = session
        self._pending_save = (account_id, save_name)
        self.app.push_screen(DiscoveredPicker(session.workspaces), self._after_pick)

    def _after_pick(self, ws: AccountWorkspace | None) -> None:
        if ws:
            self._do_connect_account_ws(ws)

    @work(group="login")
    async def _do_connect_account_ws(self, ws: AccountWorkspace) -> None:
        if self._account_session is None:
            return
        self._status(f"[$accent]Connecting to {ws.name}…[/]")
        account_id, save_name = getattr(self, "_pending_save", ("", ""))
        try:
            connection = await asyncio.to_thread(
                self._onboarding.connect_account_workspace,
                self._account_session,
                ws,
                account_id or None,
            )
        except AuthError as exc:
            self._status(f"[$error]Connect failed:[/] {exc}")
            return
        self.dismiss(
            ConnectResult(
                connection=connection, save=bool(save_name), save_name=save_name
            )
        )

    # -- exit -----------------------------------------------------------
    @on(Button.Pressed, "#btn-quit")
    def _quit(self) -> None:
        self.app.exit()

    def action_back(self) -> None:
        if self._can_cancel:
            self.dismiss(None)
