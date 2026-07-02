"""Drift guard: every MainScreen binding must be documented in the help."""

from __future__ import annotations

from isolinear.interface.modals import HelpScreen
from isolinear.interface.screens.main import MainScreen

# how a Textual key name reads in the hand-written help table
DISPLAY = {
    "question_mark": "?",
    "slash": "/",
    "escape": "esc",
    "up": "↑↓",
    "down": "↑↓",
    "left": "←→",
    "right": "←→",
    "shift+tab": "tab",
}


def _help_tokens() -> set[str]:
    tokens: set[str] = set()
    for key_col, _ in HelpScreen.KEYS:
        if key_col.strip() == "/":
            tokens.add("/")
        else:
            tokens.update(key_col.split())
    tokens.discard("/")  # the separator in "s / S" — re-added above when literal
    tokens.add("/")
    return tokens


def test_every_main_screen_binding_is_in_the_help():
    tokens = _help_tokens()
    for binding in MainScreen.BINDINGS:
        for key in binding.key.split(","):
            shown = DISPLAY.get(key, key)
            assert shown in tokens, (
                f"binding “{key}” ({binding.action}) is missing from "
                "HelpScreen.KEYS — update the help table"
            )
