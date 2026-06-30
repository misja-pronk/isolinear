from __future__ import annotations

from textual.widgets import Button, DataTable

from fakes import stub_onboarding
from isolinear.app import IsolinearApp
from isolinear.domain import SOURCE_BUNDLE, Workspace
from isolinear.interface.screens.login import LoginScreen, WorkspaceUrlModal


async def test_no_workspaces_lands_on_login_hub():
    app = IsolinearApp(onboarding=stub_onboarding())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LoginScreen)
        app.screen.query_one("#btn-url", Button)  # add-by-URL is the way in


async def test_url_door_opens_and_closes():
    app = IsolinearApp(onboarding=stub_onboarding())
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.click("#btn-url")
        await pilot.pause()
        assert isinstance(app.screen, WorkspaceUrlModal)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, LoginScreen)


async def test_workspaces_listed_with_sources_and_bundle_default():
    bundle = Workspace(
        host="https://dab.cloud.databricks.com",
        source=SOURCE_BUNDLE,
        target="acme",
        default=True,
    )
    onboarding = stub_onboarding(
        profiles=[Workspace(profile="prod", host="https://prod.cloud.databricks.com")],
        bundle=bundle,
    )
    app = IsolinearApp(onboarding=onboarding)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, LoginScreen)
        table = app.screen.query_one("#ws-table", DataTable)
        assert table.row_count == 2
        # the bundle target is row 0, pre-selected, and labelled as the default
        assert table.cursor_row == 0
        name, host, source = table.get_row_at(0)
        assert name == "acme"
        assert "databricks.yml" in source and "default" in source
        # the profile is listed with its own source
        assert table.get_row_at(1)[2] == "~/.databrickscfg"
