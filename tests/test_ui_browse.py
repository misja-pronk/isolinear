from __future__ import annotations

from typing import cast

from textual.widgets import DataTable

from fakes import seeded_store, stub_onboarding
from isolinear.app import IsolinearApp
from isolinear.application import WorkspaceService
from isolinear.interface.screens.login import LoginScreen
from isolinear.interface.screens.main import MainScreen
from isolinear.interface.widgets import ScopesPane


def _app_with_session() -> tuple[IsolinearApp, WorkspaceService]:
    session = WorkspaceService(seeded_store(), "test")
    return IsolinearApp(onboarding=stub_onboarding(), session=session), session


async def test_warm_populates_scopes_and_selects_first():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        assert main.query_one(ScopesPane).query_one(DataTable).row_count == 2
        # scopes are sorted -> 'kv' before 'prod'
        assert main.current_scope == "kv"


async def test_reveal_fetches_and_caches_value():
    app, session = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
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


async def test_tab_moves_focus_into_secrets_pane():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        assert getattr(app.focused, "id", None) == "secrets-table"


async def test_filter_narrows_then_clears_secrets():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")  # prod: api-key, db-password
        await pilot.press("tab")  # focus secrets
        await pilot.pause()
        table = cast(MainScreen, app.screen).secrets_pane.query_one(DataTable)
        assert table.row_count == 2
        await pilot.press("slash")  # open filter
        await pilot.pause()
        await pilot.press("d", "b")  # "db"
        await pilot.pause()
        assert table.row_count == 1  # only db-password
        await pilot.press("escape")  # clear + close
        await pilot.pause()
        assert table.row_count == 2


async def test_delete_secret_via_confirm_keeps_siblings():
    app, session = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")  # prod (api-key, db-password)
        await pilot.press("tab")  # focus secrets so 'd' targets the secret
        await pilot.pause()
        await pilot.press("d")  # confirm modal
        await pilot.press("y")  # confirm
        await app.workers.wait_for_complete()
        await pilot.pause()
        remaining = [s.key for s in session.secrets_for("prod")]
        assert remaining == ["db-password"]


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
        assert app.screen.query_one(ScopesPane).query_one(DataTable).row_count == 3
