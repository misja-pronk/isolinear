"""The 'Keystone' theme — violet-cyber, after the Star Trek LCARS palette.

Electric violet on near-black ink, cyan as the live/seal accent, amber for
caution. Construction-meets-starship.
"""

from __future__ import annotations

from textual.theme import Theme

KEYSTONE_THEME = Theme(
    name="keystone",
    primary="#7c5cff",  # electric violet — LCARS panels / active accent
    secondary="#29e0c4",  # cyan — live / unsealed / highlights
    accent="#ff9f1c",  # amber — caution / locked
    warning="#ff9f1c",
    error="#ff4d6d",  # rose — destructive
    success="#29e0c4",
    foreground="#e8e4f0",
    background="#0d0a14",  # ink
    surface="#161024",  # panels
    panel="#221a3a",  # raised panels
    dark=True,
    variables={
        "border": "#2e2350",
        "text-muted": "#8b82a8",
        "scrollbar": "#221a3a",
        "scrollbar-hover": "#7c5cff",
        "block-cursor-background": "#7c5cff",
        "block-cursor-foreground": "#0d0a14",
        "footer-key-foreground": "#29e0c4",
        "footer-background": "#0d0a14",
    },
)
