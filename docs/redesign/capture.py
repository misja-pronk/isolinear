"""Capture REAL screenshots of the live Textual app (driven by test fakes).

Not app code — a verification helper. Textual exports SVG; convert to PNG with
macOS QuickLook if you want a raster:  qlmanage -t -s 1600 -o . after-*.svg

    uv run python docs/redesign/capture.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tests"))

from fakes import seeded_store, stub_onboarding  # noqa: E402
from isolinear.app import IsolinearApp  # noqa: E402
from isolinear.application import WorkspaceService  # noqa: E402

SIZE = (112, 34)


async def shot(name: str, steps: list[str], *, with_session: bool = True) -> None:
    onboarding = stub_onboarding()
    session = WorkspaceService(seeded_store(), "prod-account") if with_session else None
    app = IsolinearApp(onboarding=onboarding, session=session)
    async with app.run_test(size=SIZE) as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        for key in steps:
            await pilot.press(key)
            await app.workers.wait_for_complete()
            await pilot.pause()
        path = app.save_screenshot(filename=name, path=HERE)
        # Textual bundles Fira Code into the SVG; re-point it at the system mono
        # (SF Mono on macOS via `ui-monospace`) so the export matches a real
        # terminal, and give the fake window chrome a system sans title.
        svg = (
            Path(path)
            .read_text()
            .replace(
                "Fira Code, monospace", "ui-monospace, SFMono-Regular, Menlo, monospace"
            )
            .replace(
                "font-family: arial",
                "font-family: ui-sans-serif, -apple-system, Helvetica Neue, sans-serif",
            )
        )
        Path(path).write_text(svg)
        print("wrote", name)


async def main() -> None:
    # main browser, prod scope, api-key revealed
    await shot("after-main.svg", ["j", "tab", "space"])
    # permissions modal for prod
    await shot("after-permissions.svg", ["j", "p"])
    # delete confirm for a secret
    await shot("after-confirm.svg", ["j", "tab", "d"])
    # login / onboarding hub
    await shot("after-login.svg", [], with_session=False)


if __name__ == "__main__":
    asyncio.run(main())
