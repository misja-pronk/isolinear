"""Browser power tools: move/copy, .env import/export, principal lookup."""

from __future__ import annotations

from typing import cast

from textual.widgets import Checkbox, DataTable, Input, Select

from fakes import FakeSecretStore, seeded_store, stub_onboarding
from isolinear.app import IsolinearApp
from isolinear.application import WorkspaceService
from isolinear.domain import Acl, Scope, Secret
from isolinear.interface.modals import MoveSecretModal, PrincipalModal
from isolinear.interface.screens.main import MainScreen


def _app() -> tuple[IsolinearApp, WorkspaceService]:
    session = WorkspaceService(seeded_store(), "test")
    return IsolinearApp(onboarding=stub_onboarding(), session=session), session


def _two_scope_app() -> tuple[IsolinearApp, WorkspaceService]:
    store = FakeSecretStore(
        scopes=[Scope("alpha"), Scope("beta")],
        secrets={"alpha": [Secret("alpha", "token", 1_718_000_000_000)], "beta": []},
        acls={
            "alpha": [Acl("me@corp.com", "MANAGE"), Acl("etl-bot", "READ")],
            "beta": [Acl("etl-bot", "WRITE")],
        },
        values={("alpha", "token"): "t0ps3cret"},
    )
    session = WorkspaceService(store, "test")
    return IsolinearApp(onboarding=stub_onboarding(), session=session), session


# ── move / rename / copy ────────────────────────────────────────────────


async def test_rename_secret_keeps_value_and_removes_original():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        original = session.reveal("prod", "api-key")
        await pilot.press("j", "tab")  # prod / api-key
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        assert isinstance(app.screen, MoveSecretModal)
        app.screen.query_one("#f-key", Input).value = "api-key-v2"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        keys = [s.key for s in session.secrets_for("prod")]
        assert "api-key-v2" in keys and "api-key" not in keys
        assert session.reveal("prod", "api-key-v2") == original


async def test_copy_secret_to_another_scope():
    app, session = _two_scope_app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("tab")  # alpha / token
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        app.screen.query_one("#f-scope", Select).value = "beta"
        app.screen.query_one("#f-keep", Checkbox).value = True
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert [s.key for s in session.secrets_for("alpha")] == ["token"]  # kept
        assert session.reveal("beta", "token") == "t0ps3cret"


async def test_move_from_keyvault_forces_copy():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("tab")  # kv / tenant-id (Key Vault-backed)
        await pilot.pause()
        await pilot.press("m")
        await pilot.pause()
        keep = app.screen.query_one("#f-keep", Checkbox)
        assert keep.value and keep.disabled  # copy is the only option
        # only non-KV scopes are offered as targets
        assert app.screen.query_one("#f-scope", Select).value == "prod"
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert any(s.key == "tenant-id" for s in session.secrets_for("kv"))  # kept
        assert any(s.key == "tenant-id" for s in session.secrets_for("prod"))


async def test_move_onto_itself_is_rejected():
    app, _ = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j", "tab", "m")
        await pilot.pause()
        await pilot.press("enter")  # same scope + same key
        await pilot.pause()
        assert isinstance(app.screen, MoveSecretModal)  # not submitted
        assert app.screen.query_one("#form-error").display
        await pilot.press("escape")


# ── .env import / export ────────────────────────────────────────────────


async def test_import_env_bulk_loads_a_scope(tmp_path):
    env = tmp_path / "app.env"
    env.write_text("A=1\nB=two\n# comment\nC='three'\n")
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")  # prod (writable)
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        main.action_import_env()
        await pilot.pause()
        app.screen.query_one("#f-path", Input).value = str(env)
        await pilot.press("enter")  # path -> confirm dialog
        await pilot.pause()
        await pilot.press("y")  # confirm import
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert session.reveal("prod", "A") == "1"
        assert session.reveal("prod", "B") == "two"
        assert session.reveal("prod", "C") == "three"


async def test_export_env_keys_is_redacted():
    app, _ = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")  # prod
        await pilot.pause()
        cast(MainScreen, app.screen).action_export_env_keys()
        await pilot.pause()
        assert app.clipboard == "api-key=\ndb-password=\n"


async def test_export_env_values_behind_confirm():
    app, session = _app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")
        await pilot.pause()
        cast(MainScreen, app.screen).action_export_env_values()
        await pilot.pause()
        await pilot.press("y")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.clipboard is not None
        assert f"api-key={session.reveal('prod', 'api-key')}" in app.clipboard


# ── principal lookup ────────────────────────────────────────────────────


async def test_principal_lookup_filters_and_jumps_to_scope():
    app, _ = _two_scope_app()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        main.action_principal_lookup()
        await pilot.pause()
        assert isinstance(app.screen, PrincipalModal)
        table = app.screen.query_one(DataTable)
        assert table.row_count == 3  # every grant in the workspace
        await pilot.press(*"etl")  # narrow to the bot
        await pilot.pause()
        assert table.row_count == 2
        # rows are highest-privilege first: row 0 is etl-bot's WRITE on beta
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        assert main.current_scope == "beta"
