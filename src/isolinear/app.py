"""Isolinear — a terminal Databricks secret manager.

The App is the composition root: it builds the infrastructure adapters, wires
them into the `OnboardingService`, installs the theme, and hands off to
`MainScreen`. Domain logic lives in `isolinear.domain`, use-cases in
`isolinear.application`, adapters in `isolinear.infrastructure`; UI in
`isolinear.interface`.
"""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from .application import OnboardingService, WorkspaceService
from .infrastructure import (
    DatabricksBundleStore,
    DatabricksCfgProfileStore,
    DatabricksConnector,
)
from .interface.screens.main import MainScreen
from .interface.theme import ISOLINEAR_THEMES


class IsolinearApp(App[None]):
    CSS_PATH = "styles.tcss"
    TITLE = "Isolinear"
    BINDINGS = [Binding("q", "quit", "Quit", show=False)]

    def __init__(
        self,
        onboarding: OnboardingService | None = None,
        session: WorkspaceService | None = None,
    ) -> None:
        super().__init__()
        self._onboarding = onboarding
        self._initial_session = session

    def get_theme_variable_defaults(self) -> dict[str, str]:
        # The stylesheet is parsed under Textual's default theme before ours is
        # applied, so the per-section accents must resolve there too. Each
        # Isolinear theme overrides these with its own values.
        return {
            **super().get_theme_variable_defaults(),
            "scopes-color": "#8b7cff",
            "secrets-color": "#4ec9e0",
            "detail-color": "#e0b24a",
            "value-color": "#5fd39a",
        }

    def on_mount(self) -> None:
        for theme in ISOLINEAR_THEMES:
            self.register_theme(theme)
        self.theme = "isolinear"
        onboarding = self._onboarding or OnboardingService(
            DatabricksConnector(),
            DatabricksCfgProfileStore(),
            DatabricksBundleStore(),
        )
        self.push_screen(MainScreen(onboarding, self._initial_session))


_USAGE = """\
isolinear — a keyboard-driven terminal UI for managing Databricks secrets.

usage: isolinear [--version] [--help]

Run with no arguments to launch the TUI. Inside: ? for help, ctrl+p for the
command palette, q to quit.
"""


def main() -> None:
    import sys

    args = sys.argv[1:]
    if {"-V", "--version"} & set(args):
        from importlib.metadata import version

        print(f"isolinear {version('isolinear')}")
        return
    if {"-h", "--help"} & set(args):
        print(_USAGE, end="")
        return
    IsolinearApp().run()


if __name__ == "__main__":
    main()
