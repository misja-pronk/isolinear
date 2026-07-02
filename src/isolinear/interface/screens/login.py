"""Login & onboarding.

One clear list of workspaces — each tagged with where it came from — plus a way
to add one by URL:

  * a Databricks Asset Bundle (`databricks.yml`) in the working dir → the default
  * every profile in `~/.databrickscfg`
  * a workspace URL you type in (OAuth browser sign-in)

Connecting a saved profile is instant; a bundle target or a typed URL opens the
browser. The blocking auth runs in a worker thread; the screen narrates progress
and dismisses with a ConnectResult the app turns into a live session.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.markup import escape
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Input, Static

from ...application import Connection, OnboardingService
from ...domain import SOURCE_PROFILE, AuthError, Workspace
from ..modals import key_label
from ..sorting import SortState


@dataclass
class ConnectResult:
    connection: Connection
    save: bool = False
    save_name: str = ""


def _trunc(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


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


class LoginScreen(Screen[ConnectResult | None]):
    """The onboarding hub: pick a workspace, or add one by URL."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=False),
        Binding("a,u", "add_url", "Add by URL", show=False),
        Binding("s", "sort", "Sort", show=False),
        Binding("S", "sort_reverse", "Sort reverse", show=False),
        Binding("q", "quit_app", "Quit", show=False),
    ]

    def __init__(
        self,
        workspaces: list[Workspace],
        onboarding: OnboardingService,
        can_cancel: bool = False,
    ) -> None:
        super().__init__()
        self._workspaces = workspaces
        self._onboarding = onboarding
        self._can_cancel = can_cancel
        self._sort = SortState(3, col=None)  # natural order (default first) at start
        self._order: list[int] = []  # display row -> index into _workspaces

    def compose(self) -> ComposeResult:
        card_classes = "browse" if self._workspaces else ""
        with Center(), Vertical(id="login-card", classes=card_classes):
            yield Static("Isolinear", id="login-wordmark")
            yield Static("[$primary]▂▂[/][$success]▂▂[/][$warning]▂▂[/]", id="login-mark")
            if self._workspaces:
                yield Static("WORKSPACES", classes="login-section")
                table: DataTable = DataTable(id="ws-table", zebra_stripes=False)
                table.cursor_type = "row"
                yield table
                yield Static(
                    "[$text-muted]enter connect  ·  s/S sort[/]", id="login-hint"
                )
            else:
                yield Static("GET STARTED", classes="login-section")
                yield Static(
                    "[$text-muted]No bundle or saved profiles found here.\n"
                    "Connect to a workspace by URL to begin.[/]",
                    id="login-empty",
                )
            with Horizontal(id="login-actions"):
                yield Button(
                    key_label("Add by URL"),
                    id="btn-url",
                    variant="default" if self._workspaces else "primary",
                )
                yield Button(key_label("Quit"), id="btn-quit")
            yield Static("", id="login-status")

    def on_mount(self) -> None:
        if self._workspaces:
            self._populate()
            self.query_one("#ws-table", DataTable).focus()
        else:
            self.query_one("#btn-url", Button).focus()

    def _populate(self) -> None:
        table = self.query_one("#ws-table", DataTable)
        keep = self._cursor_index()  # preserve the selection across a re-sort
        table.clear(columns=True)
        table.add_columns(*self._sort.labels(("Workspace", "Host", "Source")))
        self._order = self._sorted_indices()
        cursor = 0
        for row, i in enumerate(self._order):
            ws = self._workspaces[i]
            table.add_row(ws.name, _trunc(ws.host_label, 48), ws.source_label, key=str(i))
            if (keep is None and ws.default) or keep == i:
                cursor = row
        table.move_cursor(row=cursor)

    def _sorted_indices(self) -> list[int]:
        """Row order for the current sort; natural order (default first) if unsorted."""
        fields = (
            lambda i: self._workspaces[i].name.lower(),
            lambda i: self._workspaces[i].host_label.lower(),
            lambda i: self._workspaces[i].source_label.lower(),
        )
        return self._sort.apply(range(len(self._workspaces)), fields)

    def _cursor_index(self) -> int | None:
        """Original index of the currently-selected workspace (survives a re-sort)."""
        if not self._order:
            return None
        row = self.query_one("#ws-table", DataTable).cursor_row
        return self._order[row] if 0 <= row < len(self._order) else None

    def action_sort(self) -> None:
        self._sort.cycle()
        self._populate()

    def action_sort_reverse(self) -> None:
        self._sort.flip()
        self._populate()

    @on(DataTable.HeaderSelected, "#ws-table")
    def _sort_by_header(self, event: DataTable.HeaderSelected) -> None:
        self._sort.click(event.column_index)
        self._populate()

    def _status(self, text: str) -> None:
        self.query_one("#login-status", Static).update(text)

    # -- connect a listed workspace -------------------------------------
    @on(DataTable.RowSelected, "#ws-table")
    def _row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value  # the workspace's original index (survives sorting)
        if key is not None:
            self._connect(self._workspaces[int(key)])

    @work(group="login")
    async def _connect(self, ws: Workspace) -> None:
        opening = (
            "" if ws.source == SOURCE_PROFILE and ws.profile else " (opening browser)"
        )
        self._status(f"[$accent]Connecting to {escape(ws.name)}…{opening}[/]")
        try:
            connection = await asyncio.to_thread(self._onboarding.connect, ws)
        except AuthError as exc:
            self._status(f"[$error]Connection failed:[/] {escape(str(exc))}")
            return
        self.dismiss(ConnectResult(connection=connection))

    # -- add by URL -----------------------------------------------------
    def action_add_url(self) -> None:
        self.app.push_screen(WorkspaceUrlModal(), self._after_url_form)

    @on(Button.Pressed, "#btn-url")
    def _url(self) -> None:
        self.action_add_url()

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

    # -- exit -----------------------------------------------------------
    @on(Button.Pressed, "#btn-quit")
    def _quit(self) -> None:
        self.action_quit_app()

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_back(self) -> None:
        if self._can_cancel:
            self.dismiss(None)
