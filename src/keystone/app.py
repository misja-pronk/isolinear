"""Keystone — a terminal Databricks secret manager.

The App is the composition root: it builds the infrastructure adapters, wires
them into the `OnboardingService`, installs the theme, and hands off to
`MainScreen`. Domain logic lives in `keystone.domain`, use-cases in
`keystone.application`, adapters in `keystone.infrastructure`; UI in
`keystone.interface`.
"""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from .application import OnboardingService, WorkspaceService
from .infrastructure import DatabricksCfgProfileStore, DatabricksConnector
from .interface.screens.main import MainScreen
from .interface.theme import KEYSTONE_THEMES


class KeystoneApp(App[None]):
    CSS_PATH = "styles.tcss"
    TITLE = "Keystone"
    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(
        self,
        onboarding: OnboardingService | None = None,
        session: WorkspaceService | None = None,
    ) -> None:
        super().__init__()
        self._onboarding = onboarding
        self._initial_session = session

    def on_mount(self) -> None:
        for theme in KEYSTONE_THEMES:
            self.register_theme(theme)
        self.theme = "keystone"
        onboarding = self._onboarding or OnboardingService(
            DatabricksConnector(), DatabricksCfgProfileStore()
        )
        self.push_screen(MainScreen(onboarding, self._initial_session))


def main() -> None:
    KeystoneApp().run()


if __name__ == "__main__":
    main()
