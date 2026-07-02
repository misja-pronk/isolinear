"""Settings persistence — the JSON store and the app wiring."""

from __future__ import annotations

from typing import cast

from fakes import seeded_store, stub_onboarding
from isolinear.app import IsolinearApp
from isolinear.application import WorkspaceService
from isolinear.domain import Settings
from isolinear.infrastructure import JsonSettingsStore
from isolinear.interface.screens.main import MainScreen


def test_json_store_round_trip(tmp_path):
    store = JsonSettingsStore(tmp_path / "settings.json")
    store.save(Settings(theme="phosphor", show_all_scopes=True, audit_threshold=180))
    loaded = store.load()
    assert loaded == Settings(theme="phosphor", show_all_scopes=True, audit_threshold=180)


def test_json_store_tolerates_missing_and_corrupt_files(tmp_path):
    assert JsonSettingsStore(tmp_path / "nope.json").load() == Settings()
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert JsonSettingsStore(bad).load() == Settings()
    wrong_types = tmp_path / "types.json"
    wrong_types.write_text('{"theme": 7, "show_all_scopes": "yes", "extra": 1}')
    assert JsonSettingsStore(wrong_types).load() == Settings()


def _app(store: JsonSettingsStore) -> IsolinearApp:
    session = WorkspaceService(seeded_store(), "test")
    return IsolinearApp(
        onboarding=stub_onboarding(), session=session, settings_store=store
    )


async def test_theme_choice_survives_restart(tmp_path):
    store = JsonSettingsStore(tmp_path / "settings.json")
    app = _app(store)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        app.theme = "textual-dark"
        await pilot.pause()
    assert store.load().theme == "textual-dark"
    fresh = _app(store)
    async with fresh.run_test() as pilot:
        await fresh.workers.wait_for_complete()
        await pilot.pause()
        assert fresh.theme == "textual-dark"


async def test_scope_toggle_survives_restart(tmp_path):
    store = JsonSettingsStore(tmp_path / "settings.json")
    app = _app(store)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("f")  # show all scopes
        await pilot.pause()
    assert store.load().show_all_scopes is True
    fresh = _app(store)
    async with fresh.run_test() as pilot:
        await fresh.workers.wait_for_complete()
        await pilot.pause()
        assert cast(MainScreen, fresh.screen).show_all_scopes is True


async def test_audit_threshold_survives_restart(tmp_path):
    store = JsonSettingsStore(tmp_path / "settings.json")
    app = _app(store)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        await pilot.press("A")  # audit at the default 90d
        await pilot.press("t")  # -> 180d
        await pilot.press("escape")
        await pilot.pause()
    assert store.load().audit_threshold == 180
