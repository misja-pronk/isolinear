"""Capture REAL screenshots of the live Textual app (driven by test fakes).

Not app code — a docs helper. Textual exports SVG with a transparent page
background, which we serve directly (docs/img/*.svg + the README) so the
terminal window floats cleanly over any page, in light or dark mode — no white
or coloured box. Regenerate and copy into place with:

    uv run python docs/redesign/capture.py
    cp docs/redesign/after-main.svg        docs/img/browse.svg
    cp docs/redesign/after-login.svg       docs/img/login.svg
    cp docs/redesign/after-auth.svg        docs/img/auth.svg
    cp docs/redesign/after-permissions.svg docs/img/perms.svg
    cp docs/redesign/after-confirm.svg     docs/img/confirm.svg
    cp docs/redesign/after-login-empty.svg docs/img/login-empty.svg
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
from isolinear.domain import SOURCE_BUNDLE, Workspace  # noqa: E402

SIZE = (112, 34)


async def shot(
    name: str, steps: list[str], *, with_session: bool = True, onboarding=None
) -> None:
    onboarding = onboarding or stub_onboarding()
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
    # authorization overview
    await shot("after-auth.svg", ["a"])
    # login empty state — no bundle, no profiles
    await shot("after-login-empty.svg", [], with_session=False)
    # login / onboarding hub — a bundle (default) plus ~/.databrickscfg profiles
    login = stub_onboarding(
        profiles=[
            Workspace(profile="prod", host="https://prod.cloud.databricks.com"),
            Workspace(profile="staging", host="https://staging.cloud.databricks.com"),
        ],
        bundle=Workspace(
            host="https://acme-dev.cloud.databricks.com",
            source=SOURCE_BUNDLE,
            target="acme-platform",
            default=True,
        ),
    )
    await shot("after-login.svg", [], with_session=False, onboarding=login)


if __name__ == "__main__":
    asyncio.run(main())
