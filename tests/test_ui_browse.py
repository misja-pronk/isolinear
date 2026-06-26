from __future__ import annotations

from textual.widgets import ListView

from dbxvault.app import VaultApp
from dbxvault.core import WorkspaceSession
from dbxvault.ui.screens.login import LoginScreen
from dbxvault.ui.widgets import ScopesPane
from fakes import seeded_gateway


def _app_with_session() -> tuple[VaultApp, WorkspaceSession]:
    session = WorkspaceSession(seeded_gateway(), "test")
    return VaultApp(profiles=[], session=session), session


async def test_warm_populates_scopes_and_selects_first():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = app.screen
        assert len(main.query_one(ScopesPane).query_one(ListView)) == 2
        # scopes are sorted -> 'kv' before 'prod'
        assert main.current_scope == "kv"


async def test_reveal_fetches_and_caches_value():
    app, session = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = app.screen
        await pilot.press("tab")  # focus the secrets table
        await pilot.pause()
        assert main.current_secret == "tenant-id"

        await pilot.press("space")  # reveal
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert main._revealed == ("kv", "tenant-id")
        assert session.cached_value("kv", "tenant-id") is not None


async def test_auth_overview_opens():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "AuthScreen"


async def test_w_opens_workspace_switcher():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("w")
        await pilot.pause()
        assert isinstance(app.screen, LoginScreen)


async def test_new_scope_via_modal_updates_pane():
    app, session = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("N")  # new scope
        await pilot.pause()
        await pilot.press("s", "t", "a", "g", "e")
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert any(s.name == "stage" for s in session.scopes)
        assert len(app.screen.query_one(ScopesPane).query_one(ListView)) == 3
