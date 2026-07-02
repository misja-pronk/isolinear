"""Visual regression snapshots (pytest-textual-snapshot).

Each test renders the real app (driven by the fakes) to SVG and compares it to
the committed baseline in __snapshots__/. When a UI change is intentional,
regenerate with:

    uv run pytest tests/test_snapshots.py --snapshot-update
"""

from __future__ import annotations

from fakes import seeded_store, stub_onboarding
from isolinear.app import IsolinearApp
from isolinear.application import WorkspaceService

SIZE = (110, 30)


async def _settle(pilot) -> None:
    """Let the startup warm (and any other worker) finish before rendering."""
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def _app(*, session: bool = True) -> IsolinearApp:
    svc = WorkspaceService(seeded_store(), "test") if session else None
    return IsolinearApp(onboarding=stub_onboarding(), session=svc)


def test_browse_screen(snap_compare):
    assert snap_compare(
        _app(), press=["j", "tab"], run_before=_settle, terminal_size=SIZE
    )


def test_login_empty_state(snap_compare):
    assert snap_compare(_app(session=False), run_before=_settle, terminal_size=SIZE)


def test_audit_screen(snap_compare):
    assert snap_compare(_app(), press=["A"], run_before=_settle, terminal_size=SIZE)
