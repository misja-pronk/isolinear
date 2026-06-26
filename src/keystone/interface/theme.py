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

# LCARS amber — the classic Okudagram orange/blue on black.
KEYSTONE_AMBER = Theme(
    name="keystone-amber",
    primary="#ff9f43",  # LCARS amber
    secondary="#6bb6ff",  # LCARS blue
    accent="#ffd166",
    warning="#ffd166",
    error="#e8504f",
    success="#6bb6ff",
    foreground="#f3ead9",
    background="#0a0a0a",
    surface="#15110a",
    panel="#241a0e",
    dark=True,
    variables={
        "border": "#3a2a14",
        "text-muted": "#9a8e76",
        "block-cursor-background": "#ff9f43",
        "block-cursor-foreground": "#0a0a0a",
        "footer-key-foreground": "#6bb6ff",
        "footer-background": "#0a0a0a",
    },
)

# Phosphor green — a spare retro-terminal look.
KEYSTONE_PHOSPHOR = Theme(
    name="keystone-phosphor",
    primary="#5ad27a",
    secondary="#9ad29a",
    accent="#d7d77a",
    warning="#d7d77a",
    error="#d2705a",
    success="#5ad27a",
    foreground="#c8d2c8",
    background="#070b07",
    surface="#0e150e",
    panel="#152115",
    dark=True,
    variables={
        "border": "#1d2d1d",
        "text-muted": "#6f896f",
        "block-cursor-background": "#5ad27a",
        "block-cursor-foreground": "#070b07",
        "footer-key-foreground": "#9ad29a",
        "footer-background": "#070b07",
    },
)

KEYSTONE_THEMES = [KEYSTONE_THEME, KEYSTONE_AMBER, KEYSTONE_PHOSPHOR]
