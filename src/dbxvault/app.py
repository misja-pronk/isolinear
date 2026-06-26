"""Vault — a terminal Databricks secret manager.

The App is deliberately thin: it installs the theme and the stylesheet and hands
off to `MainScreen`, which owns the browsing experience. All domain logic lives
in `dbxvault.core`; all UI in `dbxvault.ui`.
"""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from .core import WorkspaceSession, discover_workspaces
from .ui.screens.main import MainScreen
from .ui.theme import VAULT_THEME


class VaultApp(App[None]):
    CSS_PATH = "styles.tcss"
    TITLE = "Vault"
    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(
        self,
        profiles=None,
        session: WorkspaceSession | None = None,
    ) -> None:
        super().__init__()
        self._initial_profiles = profiles
        self._initial_session = session

    def on_mount(self) -> None:
        self.register_theme(VAULT_THEME)
        self.theme = "vault"
        profiles = (
            self._initial_profiles
            if self._initial_profiles is not None
            else discover_workspaces()
        )
        self.push_screen(MainScreen(profiles, self._initial_session))


def main() -> None:
    VaultApp().run()


if __name__ == "__main__":
    main()
