"""The distinct 'Vault' theme — deep navy with teal/amber accents.

Superfile-inspired in layout, but its own identity: a cold vault-navy base,
teal as the active accent, amber for caution, crimson for destructive actions.
"""

from __future__ import annotations

from textual.theme import Theme

VAULT_THEME = Theme(
    name="vault",
    primary="#2ec4b6",  # teal — active selection / accents
    secondary="#5bc0eb",  # sky — secondary highlights
    accent="#ffb703",  # amber — caution / locked
    warning="#ffb703",
    error="#e63946",  # crimson — destructive
    success="#43aa8b",
    foreground="#e0e6ed",
    background="#0b1622",  # vault navy
    surface="#13202e",  # panels
    panel="#1b2d3f",  # raised panels
    dark=True,
    variables={
        "border": "#23394d",
        "text-muted": "#7d93a8",
        "scrollbar": "#1b2d3f",
        "scrollbar-hover": "#2ec4b6",
        "block-cursor-background": "#2ec4b6",
        "block-cursor-foreground": "#0b1622",
        "footer-key-foreground": "#2ec4b6",
        "footer-background": "#0b1622",
    },
)
