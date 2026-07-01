"""Isolinear themes.

The default is **Graphite** — a calm, near-neutral base with a single restrained
violet accent (focus + selection), green for a revealed value, red for
destructive actions. Built for enterprise: colour means something, so it's rare.

The violet / amber / phosphor palettes live on as optional "fun" skins (cycle
with the command palette → "Change theme").
"""

from __future__ import annotations

from textual.theme import Theme

# Graphite — the calm, enterprise default.
ISOLINEAR_GRAPHITE = Theme(
    name="isolinear",
    primary="#8b7cff",  # violet — the one accent: focus + selection
    secondary="#9b8cff",  # lighter violet — focused titles, footer keys
    accent="#5fd39a",  # green — a revealed / live value
    warning="#e2b341",  # muted amber
    error="#f07269",  # soft red — destructive
    success="#5fd39a",
    foreground="#e9e9ef",
    background="#0d0d11",  # near-neutral graphite ink
    surface="#15151b",  # panels
    panel="#1c1c24",  # raised panels
    dark=True,
    variables={
        "border": "#26262f",
        "text-muted": "#8a8a97",
        "scrollbar": "#1c1c24",
        "scrollbar-hover": "#8b7cff",
        "block-cursor-background": "#8b7cff",
        "block-cursor-foreground": "#0d0d11",
        "footer-key-foreground": "#9b8cff",
        "footer-background": "#0d0d11",
        # per-section accents (scopes / secrets / detail)
        "scopes-color": "#8b7cff",
        "secrets-color": "#4ec9e0",
        "detail-color": "#e0b24a",
        "value-color": "#5fd39a",  # green — a revealed / live value
    },
)

# Violet-cyber — the original electric LCARS-flavoured look.
ISOLINEAR_VIOLET = Theme(
    name="isolinear-violet",
    primary="#7c5cff",
    secondary="#29e0c4",
    accent="#ff9f1c",
    warning="#ff9f1c",
    error="#ff4d6d",
    success="#29e0c4",
    foreground="#e8e4f0",
    background="#0d0a14",
    surface="#161024",
    panel="#221a3a",
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
        "scopes-color": "#7c5cff",
        "secrets-color": "#29e0c4",
        "detail-color": "#ff9f1c",
        "value-color": "#4ee39a",
    },
)

# LCARS amber — the classic Okudagram orange/blue on black.
ISOLINEAR_AMBER = Theme(
    name="isolinear-amber",
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
        "scopes-color": "#ff9f43",
        "secrets-color": "#6bb6ff",
        "detail-color": "#ffd166",
        "value-color": "#5ad19b",
    },
)

# Phosphor green — a spare retro-terminal look.
ISOLINEAR_PHOSPHOR = Theme(
    name="isolinear-phosphor",
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
        "scopes-color": "#5ad27a",
        "secrets-color": "#82c8b0",
        "detail-color": "#d7d77a",
        "value-color": "#7fd6c0",
    },
)

ISOLINEAR_THEMES = [
    ISOLINEAR_GRAPHITE,
    ISOLINEAR_VIOLET,
    ISOLINEAR_AMBER,
    ISOLINEAR_PHOSPHOR,
]
