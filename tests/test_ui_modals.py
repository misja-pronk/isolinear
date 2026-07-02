"""End-to-end modal tests (Textual Pilot).

Two guards, together covering the 'rendering artifacts' regression where the
new-secret / change-permission dialogs showed a garbled title and blank fields:

1. Every modal card must be OPAQUE. The backdrop above it is translucent
   ($background 88%), so a card without a solid fill lets the dimmed main
   screen bleed through and garble the title + inputs on real terminals.
2. The form inputs must capture what the user types and round-trip it out.
"""

from __future__ import annotations

from textual.widgets import Input

from fakes import seeded_store, stub_onboarding
from isolinear.app import IsolinearApp
from isolinear.application import WorkspaceService
from isolinear.interface.modals import (
    AclFormModal,
    AuthScreen,
    ConfirmModal,
    HelpScreen,
    PermissionsScreen,
    ScopeFormModal,
    SecretFormModal,
)


def _app() -> tuple[IsolinearApp, WorkspaceService]:
    session = WorkspaceService(seeded_store(), "test")
    return IsolinearApp(onboarding=stub_onboarding(), session=session), session


async def test_every_modal_card_is_opaque():
    """The dialog card must fully occlude the translucent backdrop — otherwise
    the dimmed main screen bleeds through it and garbles the contents."""
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        modals = [
            SecretFormModal(scope="kv"),
            SecretFormModal(scope="kv", key="tenant-id", edit=True),
            ScopeFormModal(),
            AclFormModal(scope="kv"),
            AclFormModal(principal="users", permission="READ", edit=True, scope="kv"),
            ConfirmModal("Delete secret", "Permanently delete tenant-id."),
            HelpScreen(),
            AuthScreen(session.identity, session.auth_summary()),
            PermissionsScreen(session, "kv"),
        ]
        for modal in modals:
            app.push_screen(modal)
            await pilot.pause()
            card = app.screen.query_one("#dialog")
            alpha = card.styles.background.a
            assert alpha == 1.0, (
                f"{type(modal).__name__}: #dialog card is translucent "
                f"(alpha={alpha}) — the dimmed main screen bleeds through it"
            )
            app.pop_screen()
            await pilot.pause()


async def test_new_secret_captures_typed_key_and_value():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")  # kv is Key Vault-backed (read-only) — use prod
        await pilot.pause()
        await pilot.press("n")  # new secret in the current scope (prod)
        await pilot.pause()
        assert isinstance(app.screen, SecretFormModal)
        await pilot.press(*"token")  # into the focused key field
        assert app.screen.query_one("#f-key", Input).value == "token"
        await pilot.press("tab")  # move to the value field
        await pilot.press(*"s3cret")
        assert app.screen.query_one("#f-value", Input).value == "s3cret"
        await pilot.press("enter")  # submit
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "token" in [s.key for s in session.secrets_for("prod")]
        assert session.reveal("prod", "token") == "s3cret"


async def test_edit_with_empty_value_does_not_submit():
    """Submitting an edit with a blank value would silently wipe the secret."""
    app, _ = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        app.push_screen(SecretFormModal(scope="kv", key="tenant-id", edit=True))
        await pilot.pause()
        await pilot.press("enter")  # value field is empty — must not submit
        await pilot.pause()
        assert isinstance(app.screen, SecretFormModal)
        await pilot.press(*"n3w-value")
        await pilot.press("enter")  # with a value it submits normally
        await pilot.pause()
        assert not isinstance(app.screen, SecretFormModal)


async def test_q_inside_a_dialog_does_not_quit_the_app():
    """`q` quits from the browse screen only — from a dialog (focus on a
    button, so no Input swallows it) it must not bubble into an app quit."""
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        app.push_screen(ConfirmModal("Delete secret", "Permanently delete."))
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert app.is_running
        assert isinstance(app.screen, ConfirmModal)
        await pilot.press("escape")
        await pilot.pause()
        app.push_screen(PermissionsScreen(session, "kv"))
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        assert app.is_running
        assert isinstance(app.screen, PermissionsScreen)


async def test_grant_permission_captures_typed_principal():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("p")  # permissions editor for kv
        await pilot.pause()
        await pilot.press("a")  # add
        await pilot.pause()
        assert isinstance(app.screen, AclFormModal)
        await pilot.press(*"botuser")
        assert app.screen.query_one("#f-principal", Input).value == "botuser"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert any(a.principal == "botuser" for a in session.acls_for("kv"))
