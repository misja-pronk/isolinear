from __future__ import annotations

from textual.widgets import Input, Select

from fakes import seeded_store, stub_onboarding
from keystone.app import KeystoneApp
from keystone.application import WorkspaceService
from keystone.interface.modals import AclFormModal, PermissionsScreen


def _app() -> tuple[KeystoneApp, WorkspaceService]:
    session = WorkspaceService(seeded_store(), "test")
    return KeystoneApp(onboarding=stub_onboarding(), session=session), session


async def test_p_opens_permissions_for_current_scope():
    app, _ = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, PermissionsScreen)


async def test_add_permission_via_form():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("p")  # permissions editor (scope 'kv')
        await pilot.pause()
        await pilot.press("a")  # add
        await pilot.pause()
        assert isinstance(app.screen, AclFormModal)
        app.screen.query_one("#f-principal", Input).value = "bot@corp.com"
        app.screen.query_one("#f-permission", Select).value = "WRITE"
        await pilot.press("enter")  # submit form
        await app.workers.wait_for_complete()
        await pilot.pause()
        perms = {a.principal: a.permission for a in session.acls_for("kv")}
        assert perms.get("bot@corp.com") == "WRITE"


async def test_remove_permission():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("p")  # scope 'kv' has principal 'users'
        await pilot.pause()
        await pilot.press("d")  # remove highlighted row
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert session.acls_for("kv") == []


async def test_command_palette_opens():
    app, _ = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert "CommandPalette" in app.screen.__class__.__name__
