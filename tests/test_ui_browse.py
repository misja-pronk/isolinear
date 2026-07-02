from __future__ import annotations

from typing import cast

from textual.widgets import DataTable

from fakes import seeded_store, stub_onboarding
from isolinear.app import IsolinearApp
from isolinear.application import WorkspaceService
from isolinear.interface.modals import ConfirmModal
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


async def test_sorting_scopes_preserves_revealed_secret():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        await pilot.press("j")  # scopes: kv -> prod
        await pilot.press("tab")  # focus secrets
        await pilot.press("j")  # secrets: api-key -> db-password
        await pilot.pause()
        chosen = main.current_secret
        await pilot.press("space")  # reveal it
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert main._revealed is not None
        await pilot.press("h")  # focus the scopes pane again
        await pilot.press("s")  # sort scopes — must not reset the secret/reveal
        await pilot.pause()
        assert main.current_secret == chosen
        assert main._revealed is not None


async def test_sorting_secrets_preserves_revealed_secret():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        await pilot.press("j")  # scopes: kv -> prod
        await pilot.press("tab")  # focus secrets
        await pilot.press("j")  # secrets: api-key -> db-password
        await pilot.pause()
        chosen = main.current_secret
        await pilot.press("space")  # reveal it
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("s")  # sort secrets — cursor + reveal must hold
        await pilot.pause()
        assert main.current_secret == chosen
        assert main._revealed is not None


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


async def test_enter_on_secret_toggles_reveal():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        await pilot.press("j")  # prod
        await pilot.press("tab")  # focus secrets (api-key)
        await pilot.pause()
        await pilot.press("enter")  # reveal
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert main._revealed == ("prod", "api-key")
        await pilot.press("enter")  # hide again
        await pilot.pause()
        assert main._revealed is None


async def test_keyvault_scope_blocks_secret_mutations():
    """Scope 'kv' is Azure Key Vault-backed: n/e must not open the form."""
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("n")  # blocked — the binding is disabled
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        await pilot.press("tab")  # focus secrets (tenant-id)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_filter_survives_enter_and_esc_clears_it():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        await pilot.press("j")  # prod: api-key, db-password
        await pilot.press("tab")
        await pilot.pause()
        table = main.secrets_pane.query_one(DataTable)
        await pilot.press("slash")
        await pilot.press("d", "b")
        await pilot.press("enter")  # pin the filter, back to the table
        await pilot.pause()
        assert table.row_count == 1
        assert main.secrets_pane.query_one("#secrets-filter").display  # chip shows it
        await pilot.press("r")  # refresh the scope — the filter must survive
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert table.row_count == 1
        await pilot.press("escape")  # esc on the filtered table clears it
        await pilot.pause()
        assert table.row_count == 2
        assert not main.secrets_pane.query_one("#secrets-filter").display


async def test_arrows_navigate_the_list_while_filtering():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        await pilot.press("j")  # prod
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("slash")  # filter bar takes focus
        await pilot.press("down")  # ...but ↓ still moves the table cursor
        await pilot.pause()
        assert main.current_secret == "db-password"


async def test_delete_from_detail_pane_targets_the_secret():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")  # prod
        await pilot.press("tab")  # secrets (api-key)
        await pilot.press("l")  # detail pane
        await pilot.pause()
        assert getattr(app.focused, "id", None) == "detail-scroll"
        await pilot.press("d")  # footer says Delete — it must target the secret
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        assert app.screen._title == "Delete secret"
        await pilot.press("escape")


async def test_global_search_jumps_to_the_secret():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        await pilot.press("ctrl+f")  # search everywhere (current scope is kv)
        await pilot.pause()
        await pilot.press(*"dbpass")  # fuzzy: prod/db-password
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert main.current_scope == "prod"
        assert main.current_secret == "db-password"
        assert getattr(app.focused, "id", None) == "secrets-table"


async def test_copy_reference_puts_snippet_on_clipboard():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("tab")  # secrets pane: kv/tenant-id selected
        await pilot.pause()
        await pilot.press("C")  # snippet picker, first row = dbutils
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.clipboard == 'dbutils.secrets.get(scope="kv", key="tenant-id")'


async def test_revealed_value_auto_hides():
    app, _ = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        main.REVEAL_TIMEOUT = 0.2
        await pilot.press("j", "tab")  # prod / api-key
        await pilot.pause()
        await pilot.press("space")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert main._hide_timer is not None  # the auto-hide is armed
        await pilot.pause(0.6)  # ...and it fires
        assert main._revealed is None


async def test_undo_restores_a_deleted_secret():
    app, session = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        original = session.reveal("prod", "api-key")
        await pilot.press("j", "tab")  # prod / api-key
        await pilot.pause()
        await pilot.press("d", "y")  # delete + confirm
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "api-key" not in [s.key for s in session.secrets_for("prod")]
        await pilot.press("u")  # undo
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "api-key" in [s.key for s in session.secrets_for("prod")]
        assert session.reveal("prod", "api-key") == original


async def test_read_only_mode_blocks_mutations():
    session = WorkspaceService(seeded_store(), "test")
    app = IsolinearApp(onboarding=stub_onboarding(), session=session, read_only=True)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")  # prod (Databricks-backed, normally writable)
        await pilot.pause()
        await pilot.press("n")  # blocked
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        await pilot.press("tab")
        await pilot.pause()
        await pilot.press("d")  # blocked too
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        assert len(session.secrets_for("prod")) == 2


async def test_forget_values_purges_the_cache():
    app, session = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        main = cast(MainScreen, app.screen)
        await pilot.press("j", "tab")
        await pilot.pause()
        await pilot.press("space")  # reveal caches the value
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert session.cached_value("prod", "api-key") is not None
        main.action_forget_values()
        await pilot.pause()
        assert session.cached_value("prod", "api-key") is None
        assert main._revealed is None


async def test_double_d_does_not_confirm_delete():
    """`d` opens the confirm dialog; a vim-twitch second `d` must not confirm."""
    app, session = _app_with_session()
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("j")  # prod (api-key, db-password)
        await pilot.press("tab")  # focus secrets so 'd' targets the secret
        await pilot.pause()
        await pilot.press("d")  # confirm modal
        await pilot.press("d")  # repeat — must be ignored
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
        keys = [s.key for s in session.secrets_for("prod")]
        assert keys == ["api-key", "db-password"]
        await pilot.press("escape")


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
