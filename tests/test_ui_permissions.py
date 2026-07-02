from __future__ import annotations

from textual.widgets import Input, Select

from fakes import seeded_store, stub_onboarding
from isolinear.app import IsolinearApp
from isolinear.application import WorkspaceService
from isolinear.interface.modals import AclFormModal, ConfirmModal, PermissionsScreen


def _app() -> tuple[IsolinearApp, WorkspaceService]:
    session = WorkspaceService(seeded_store(), "test")
    return IsolinearApp(onboarding=stub_onboarding(), session=session), session


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


async def test_remove_permission_requires_confirm():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("p")  # scope 'kv' has principal 'users'
        await pilot.pause()
        await pilot.press("d")  # opens the confirm dialog — nothing removed yet
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        assert any(a.principal == "users" for a in session.acls_for("kv"))
        await pilot.press("y")  # confirm
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert session.acls_for("kv") == []


async def test_remove_permission_can_be_cancelled():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("escape")  # back out — the grant must survive
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(app.screen, PermissionsScreen)
        assert any(a.principal == "users" for a in session.acls_for("kv"))


async def test_removing_your_own_access_warns():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        session.set_acl("kv", "me@corp.com", "MANAGE")  # the fake identity's user
        await pilot.press("p")  # default sort: highest access first -> me on top
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        assert "This is you" in app.screen._message
        await pilot.press("escape")


async def test_command_palette_opens():
    app, _ = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert "CommandPalette" in app.screen.__class__.__name__
