from __future__ import annotations

from textual.widgets import Button

from keystone.app import KeystoneApp
from keystone.ui.screens.login import AccountModal, LoginScreen, WorkspaceUrlModal


async def test_no_profiles_lands_on_login_hub():
    app = KeystoneApp(profiles=[])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LoginScreen)
        app.screen.query_one("#btn-url", Button)
        app.screen.query_one("#btn-account", Button)


async def test_login_doors_open_and_close_modals():
    app = KeystoneApp(profiles=[])
    async with app.run_test() as pilot:
        await pilot.pause()

        await pilot.click("#btn-url")
        await pilot.pause()
        assert isinstance(app.screen, WorkspaceUrlModal)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, LoginScreen)

        await pilot.click("#btn-account")
        await pilot.pause()
        assert isinstance(app.screen, AccountModal)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, LoginScreen)
