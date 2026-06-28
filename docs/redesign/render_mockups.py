"""Render redesign mockups for Isolinear as terminal-screenshot-style PNGs.

This is a DESIGN tool, not app code. It draws proposed UI states on a fake
macOS terminal window so we can react to a clean/minimal direction before
touching the real Textual code.

Run via the project toolchain (no installs into the project):

    uv run --with pillow python docs/redesign/render_mockups.py

Outputs PNGs next to this file.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

# ── render scale ────────────────────────────────────────────────────────────
S = 2  # supersample, downscaled 0.5 at the end for crisp text + 1px rules
FS = 17 * S
HERE = os.path.dirname(os.path.abspath(__file__))


# ── fonts ───────────────────────────────────────────────────────────────────
def _load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont, str]:
    sf = "/System/Library/Fonts/SFNSMono.ttf"
    if os.path.exists(sf):
        try:
            reg = ImageFont.truetype(sf, FS)
            bold = ImageFont.truetype(sf, FS)
            bold.set_variation_by_name("Bold")
            reg.set_variation_by_name("Regular")
            return reg, bold, "SF Mono"
        except OSError:
            pass
    fc = "/System/Library/Fonts/Supplemental/"
    return (
        ImageFont.truetype(fc + "FiraCode-Regular.ttf", FS),
        ImageFont.truetype(fc + "FiraCode-Bold.ttf", FS),
        "Fira Code",
    )


REG, BOLD, FONT_NAME = _load_fonts()


# ── colour helpers ──────────────────────────────────────────────────────────
def _h(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def blend(fg: str, bg: str, a: float) -> tuple[int, int, int]:
    f, b = _h(fg), _h(bg)
    return tuple(round(b[i] + (f[i] - b[i]) * a) for i in range(3))  # type: ignore


def _c(color) -> tuple[int, int, int]:
    """Normalise a colour given as a hex string or an RGB tuple."""
    return _h(color) if isinstance(color, str) else color


# Graphite — the calm, enterprise default. One restrained violet accent.
GRAPHITE = {
    "bg": "#0d0d11",
    "fg": "#e9e9ef",
    "boldfg": "#f4f4f8",
    "dim": "#8a8a97",
    "dim2": "#54545d",
    "line": "#26262f",
    "accent": "#8b7cff",
    "accent_dim": "#544c86",
    "green": "#5fd39a",
    "red": "#f07269",
}

# Optional "fun" theme accents, used only for the theme strip.
THEME_ACCENTS = [
    ("Graphite", "#8b7cff", "#0d0d11"),
    ("Violet", "#7c5cff", "#0d0a14"),
    ("Amber", "#ff9f43", "#0a0a0a"),
    ("Phosphor", "#5ad27a", "#070b07"),
]


# ── terminal canvas ─────────────────────────────────────────────────────────
class Term:
    """A fake macOS terminal window with a character grid."""

    def __init__(self, cols: int, rows: int, pal: dict[str, str] | None = None):
        self.cols, self.rows = cols, rows
        self.pal = pal or GRAPHITE
        self.cw = round(REG.getlength("0"))
        self.ch = round(FS * 1.52)
        self.pad = 26 * S  # padding between window edge and grid
        self.title_h = 30 * S
        self.margin = 26 * S  # desktop margin around the window
        self.win_w = self.cols * self.cw + self.pad * 2
        self.win_h = self.rows * self.ch + self.pad * 2 + self.title_h
        self.W = self.win_w + self.margin * 2
        self.H = self.win_h + self.margin * 2
        self.img = Image.new("RGB", (self.W, self.H), _h("#050507"))
        self.d = ImageDraw.Draw(self.img)
        self._chrome()
        # grid origin
        self.x0 = self.margin + self.pad
        self.y0 = self.margin + self.title_h + self.pad

    def _chrome(self) -> None:
        x0, y0 = self.margin, self.margin
        x1, y1 = x0 + self.win_w, y0 + self.win_h
        r = 12 * S
        # window body (rounded)
        self.d.rounded_rectangle([x0, y0, x1, y1], r, fill=_h(self.pal["bg"]))
        # title bar: rounded top, square bottom (overlap a body-coloured rect)
        self.d.rounded_rectangle(
            [x0, y0, x1, y0 + self.title_h + r], r, fill=_h("#26262c")
        )
        self.d.rectangle(
            [x0, y0 + self.title_h, x1, y0 + self.title_h + r], fill=_h(self.pal["bg"])
        )
        # hairline under the title bar
        self.d.rectangle(
            [x0, y0 + self.title_h, x1, y0 + self.title_h + 1 * S], fill=_h("#000")
        )
        # traffic lights
        cy = y0 + self.title_h // 2
        for i, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            cx = x0 + (18 + i * 20) * S
            rr = 6 * S
            self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=_h(col))
        # window title
        t = "Isolinear"
        tw = self.d.textlength(t, font=BOLD)
        self.d.text(
            (x0 + (self.win_w - tw) / 2, cy - FS * 0.62),
            t,
            font=BOLD,
            fill=_h("#b7b7c0"),
        )

    # pixel position of a cell
    def _px(self, col: float, row: float) -> tuple[float, float]:
        return self.x0 + col * self.cw, self.y0 + row * self.ch

    def text(
        self, col: float, row: float, s: str, color: str, bold: bool = False
    ) -> None:
        x, y = self._px(col, row)
        self.d.text(
            (x, y + self.ch * 0.16), s, font=BOLD if bold else REG, fill=_c(color)
        )

    def rtext(
        self, col_right: float, row: float, s: str, color: str, bold: bool = False
    ) -> None:
        w = self.d.textlength(s, font=BOLD if bold else REG)
        x, y = self._px(col_right, row)
        self.d.text(
            (x - w, y + self.ch * 0.16), s, font=BOLD if bold else REG, fill=_c(color)
        )

    def fill(
        self, col: float, row: float, ncol: float, nrow: float, color, radius: int = 0
    ) -> None:
        x, y = self._px(col, row)
        x1, y1 = x + ncol * self.cw, y + nrow * self.ch
        if radius:
            self.d.rounded_rectangle([x, y, x1, y1], radius, fill=_c(color))
        else:
            self.d.rectangle([x, y, x1, y1], fill=_c(color))

    def border(
        self, col: float, row: float, ncol: float, nrow: float, color, radius=10, w=1
    ) -> None:
        x, y = self._px(col, row)
        x1, y1 = x + ncol * self.cw, y + nrow * self.ch
        self.d.rounded_rectangle(
            [x, y, x1, y1], radius * S, outline=_c(color), width=w * S
        )

    def bar(self, col: float, row: float, nrow: float, color) -> None:
        """A thin vertical selection bar (left edge of a row)."""
        x, y = self._px(col, row)
        self.d.rectangle([x, y + 2, x + 2 * S, y + nrow * self.ch - 2], fill=_c(color))

    def hrule(self, row: float, c0: float, c1: float, color) -> None:
        x, y = self._px(c0, row)
        x1, _ = self._px(c1, row)
        self.d.rectangle([x, y, x1, y + 1 * S], fill=_c(color))

    def keys(self, col: float, row: float, items: list[tuple[str, str]]) -> None:
        p = self.pal
        x = col
        for key, label in items:
            self.text(x, row, key, p["accent"], bold=True)
            x += len(key) + 1
            self.text(x, row, label, p["dim"])
            x += len(label) + 4

    def button(
        self,
        col: float,
        row: float,
        label: str,
        *,
        filled=None,
        fg="#fff",
        border=None,
        pad: int = 2,
        h: float = 1.6,
    ) -> float:
        """A compact, vertically-centred button. Returns its width in cells."""
        w = len(label) + pad * 2
        if filled is not None:
            self.fill(col, row, w, h, filled, radius=7)
        if border is not None:
            self.border(col, row, w, h, border, radius=7)
        self.text(col + pad, row + (h - 1) / 2, label, fg, bold=filled is not None)
        return w

    def save(self, name: str) -> str:
        out = self.img.resize((self.W // S, self.H // S), Image.LANCZOS)
        path = os.path.join(HERE, name)
        out.save(path)
        return path


COLS, ROWS = 112, 32


# ── screen 1: main browser (hero) ───────────────────────────────────────────
def main_browser() -> str:
    t = Term(COLS, ROWS)
    p = t.pal

    # top bar
    t.text(0, 0, "Isolinear", p["fg"], bold=True)
    t.text(12, 0, "prod", p["dim"])
    t.text(17, 0, "/", p["dim2"])
    t.text(19, 0, "api-key", p["fg"])
    ident = "me@corp.com   ·   prod-account"
    t.rtext(COLS, 0, ident, p["dim"])
    t.hrule(1.4, 0, COLS, blend(p["line"], p["bg"], 1))

    pane_top, pane_h = 2.2, 27.0
    # geometry: scopes | secrets | detail
    sx, sw = 0, 22
    cx, cw = 24, 48
    dx, dw = 74, 38

    # --- scopes pane (unfocused) ---
    t.border(sx, pane_top, sw, pane_h, blend(p["line"], p["bg"], 1))
    t.text(sx + 2, pane_top + 1, "SCOPES", p["dim"], bold=True)
    t.text(sx + 9, pane_top + 1, "2", p["dim2"])
    # row: kv
    t.text(sx + 3, pane_top + 3, "kv", p["fg"])
    t.rtext(sx + sw - 2, pane_top + 3, "1", p["dim2"])
    # row: prod (selected, pane not focused -> faint)
    t.fill(sx + 1, pane_top + 4, sw - 2, 1, blend(p["accent"], p["bg"], 0.10))
    t.bar(sx + 1, pane_top + 4, 1, blend(p["accent"], p["bg"], 0.55))
    t.text(sx + 3, pane_top + 4, "prod", p["fg"])
    t.rtext(sx + sw - 2, pane_top + 4, "2", p["dim"])

    # --- secrets pane (FOCUSED) ---
    t.border(cx, pane_top, cw, pane_h, blend(p["accent"], p["bg"], 0.9))
    t.text(cx + 2, pane_top + 1, "SECRETS", p["boldfg"], bold=True)
    t.text(cx + 10, pane_top + 1, "prod · 2", p["dim"])
    # column header
    t.text(cx + 3, pane_top + 3, "Key", p["dim2"])
    t.text(cx + 21, pane_top + 3, "Updated", p["dim2"])
    t.text(cx + 40, pane_top + 3, "Age", p["dim2"])
    # selected + focused row
    t.fill(cx + 1, pane_top + 4, cw - 2, 1, blend(p["accent"], p["bg"], 0.20))
    t.bar(cx + 1, pane_top + 4, 1, p["accent"])
    t.text(cx + 3, pane_top + 4, "api-key", p["boldfg"], bold=True)
    t.text(cx + 21, pane_top + 4, "2024-06-10 06:13", p["dim"])
    t.text(cx + 40, pane_top + 4, "2y", p["dim"])
    # other row
    t.text(cx + 3, pane_top + 5, "db-password", p["fg"])
    t.text(cx + 21, pane_top + 5, "2024-06-16 01:06", p["dim"])
    t.text(cx + 40, pane_top + 5, "2y", p["dim"])

    # --- detail pane (unfocused) ---
    t.border(dx, pane_top, dw, pane_h, blend(p["line"], p["bg"], 1))
    t.text(dx + 2, pane_top + 1, "DETAIL", p["dim"], bold=True)
    di = dx + 3
    t.text(di, pane_top + 3, "api-key", p["boldfg"], bold=True)
    t.text(di, pane_top + 5, "Scope", p["dim"])
    t.text(di + 11, pane_top + 5, "prod", p["fg"])
    t.text(di, pane_top + 6, "Updated", p["dim"])
    t.text(di + 11, pane_top + 6, "2024-06-10 06:13", p["fg"])
    t.text(di + 28, pane_top + 6, "2y ago", p["dim2"])
    t.text(di, pane_top + 7, "Access", p["dim"])
    t.text(di + 11, pane_top + 7, "MANAGE", p["fg"])
    # value (revealed)
    t.text(di, pane_top + 9, "Value", p["dim"])
    t.text(di + 11, pane_top + 9, "revealed", p["green"])
    t.text(di, pane_top + 10, "space hide · c copy", p["dim2"])
    t.border(di, pane_top + 11, dw - 5, 2, blend(p["green"], p["bg"], 0.5), radius=6)
    t.fill(di, pane_top + 11, dw - 5, 2, blend(p["green"], p["bg"], 0.06), radius=6)
    t.text(di + 2, pane_top + 11.5, "sk_live_8f2a3c4d…b91d", p["green"])
    # permissions
    t.text(di, pane_top + 14, "Permissions", p["dim"])
    t.text(di + 12, pane_top + 14, "1", p["dim2"])
    t.text(di + 2, pane_top + 15, "users", p["fg"])
    t.rtext(dx + dw - 2, pane_top + 15, "READ", p["dim"])

    # footer
    t.keys(
        0,
        ROWS - 1,
        [
            ("space", "reveal"),
            ("c", "copy"),
            ("/", "filter"),
            ("n", "new"),
            ("?", "help"),
        ],
    )
    return t.save("01-main.png")


# ── screen 2: login / onboarding ────────────────────────────────────────────
def login() -> str:
    t = Term(COLS, ROWS)
    p = t.pal
    cardw = 56
    cl = (COLS - cardw) // 2
    top = 6
    t.border(cl, top, cardw, 19, blend(p["line"], p["bg"], 1), radius=12)
    ci = cl + 4

    def center(row, s, color, bold=False):
        w = t.d.textlength(s, font=BOLD if bold else REG) / t.cw
        t.text(cl + (cardw - w) / 2, row, s, color, bold)

    center(top + 2, "Isolinear", p["boldfg"], bold=True)
    # the one signature: a thin tri-accent rule under the wordmark
    midx = cl + cardw / 2
    seg = 4
    t.fill(midx - seg * 1.5, top + 3.3, seg, 0.12, blend(p["accent"], p["bg"], 0.9))
    t.fill(midx - seg * 0.5, top + 3.3, seg, 0.12, blend(p["green"], p["bg"], 0.8))
    t.fill(midx + seg * 0.5, top + 3.3, seg, 0.12, blend("#ff9f43", p["bg"], 0.8))
    center(top + 4, "Databricks secret management", p["dim"])

    t.text(ci, top + 6, "SAVED WORKSPACES", p["dim2"], bold=True)
    t.border(ci, top + 7, cardw - 8, 2, blend(p["line"], p["bg"], 1), radius=8)
    t.fill(ci, top + 7, cardw - 8, 2, blend(p["accent"], p["bg"], 0.10), radius=8)
    t.bar(ci, top + 7, 2, p["accent"])
    t.text(ci + 2, top + 7.5, "prod", p["fg"], bold=True)
    t.text(ci + 10, top + 7.5, "prod.cloud.databricks.com", p["dim"])

    t.text(ci, top + 11, "CONNECT", p["dim2"], bold=True)
    # primary button (filled accent)
    b1w = 17
    t.fill(ci, top + 12, b1w, 2, _h(p["accent"]), radius=8)
    t.text(ci + 2, top + 12.5, "Workspace URL", p["bg"], bold=True)
    # ghost button
    b2x = ci + b1w + 2
    b2w = 24
    t.border(b2x, top + 12, b2w, 2, blend(p["fg"], p["bg"], 0.35), radius=8)
    t.text(b2x + 2, top + 12.5, "Discover via account", p["fg"])

    t.keys(ci, top + 16, [("enter", "connect"), ("tab", "switch"), ("esc", "quit")])
    t.keys(0, ROWS - 1, [("↑↓", "select"), ("enter", "open"), ("q", "quit")])
    return t.save("02-login.png")


# ── screen 3: permissions modal ─────────────────────────────────────────────
def permissions() -> str:
    t = Term(COLS, ROWS)
    p = t.pal
    # dimmed backdrop hint (faint panes)
    for bx, bw in ((0, 22), (24, 48), (74, 38)):
        t.border(bx, 2.2, bw, 27, blend(p["line"], p["bg"], 0.5))

    cardw, cardh = 58, 13
    cl = (COLS - cardw) // 2
    top = 9
    # soft shadow
    t.fill(cl + 0.4, top + 0.5, cardw, cardh, _h("#050507"), radius=12)
    t.fill(cl, top, cardw, cardh, blend(p["fg"], p["bg"], 0.03), radius=12)
    t.border(cl, top, cardw, cardh, blend(p["fg"], p["bg"], 0.22), radius=12)
    ci = cl + 4

    t.text(ci, top + 1.5, "Permissions", p["boldfg"], bold=True)
    t.text(ci + 12, top + 1.5, "prod", p["dim"])
    t.text(ci, top + 2.7, "Who can read, write and manage this scope.", p["dim"])

    t.text(ci, top + 4.4, "Principal", p["dim2"])
    t.text(ci + 26, top + 4.4, "Permission", p["dim2"])
    rows = [("users", "READ"), ("data-eng", "MANAGE"), ("svc-etl", "WRITE")]
    for i, (who, perm) in enumerate(rows):
        ry = top + 5.4 + i
        if i == 1:
            t.fill(ci - 1, ry, cardw - 6, 1, blend(p["accent"], p["bg"], 0.18))
            t.bar(ci - 1, ry, 1, p["accent"])
        t.text(ci, ry, who, p["fg"] if i == 1 else p["fg"])
        t.text(ci + 26, ry, perm, p["dim"])

    t.keys(
        ci,
        top + cardh - 1.6,
        [("a", "add"), ("e", "change"), ("d", "remove"), ("esc", "close")],
    )
    return t.save("03-permissions.png")


# ── screen 4: delete confirm ────────────────────────────────────────────────
def confirm() -> str:
    t = Term(COLS, ROWS)
    p = t.pal
    for bx, bw in ((0, 22), (24, 48), (74, 38)):
        t.border(bx, 2.2, bw, 27, blend(p["line"], p["bg"], 0.5))

    cardw, cardh = 54, 9
    cl = (COLS - cardw) // 2
    top = 11
    t.fill(cl + 0.4, top + 0.5, cardw, cardh, _h("#050507"), radius=12)
    t.fill(cl, top, cardw, cardh, blend(p["fg"], p["bg"], 0.03), radius=12)
    t.border(cl, top, cardw, cardh, blend(p["red"], p["bg"], 0.45), radius=12)
    ci = cl + 4

    t.text(ci, top + 1.5, "Delete secret", p["red"], bold=True)
    t.text(ci, top + 3.1, "Delete", p["dim"])
    t.text(ci + 7, top + 3.1, "api-key", p["fg"], bold=True)
    t.text(ci + 15, top + 3.1, "from", p["dim"])
    t.text(ci + 20, top + 3.1, "prod.", p["fg"], bold=True)
    t.text(ci, top + 4.2, "This can't be undone.", p["dim2"])

    # buttons (right aligned): Cancel (ghost) then Delete (red, default action)
    gap = 2
    cancel_w = len("Cancel") + 4
    delete_w = len("Delete") + 4
    by = top + cardh - 2.1
    bx = cl + cardw - 3 - (cancel_w + gap + delete_w)
    t.button(bx, by, "Cancel", border=blend(p["fg"], p["bg"], 0.32), fg=p["fg"])
    t.button(bx + cancel_w + gap, by, "Delete", filled=p["red"], fg="#1a0c0c")
    return t.save("04-confirm.png")


# ── screen 5: theme strip ───────────────────────────────────────────────────
def themes() -> str:
    t = Term(COLS, 16, GRAPHITE)
    p = GRAPHITE
    t.text(0, 0, "Themes", p["fg"], bold=True)
    t.text(8, 0, "calm Graphite default · optional accents for personal use", p["dim"])
    sw = 26
    for i, (name, accent, bg) in enumerate(THEME_ACCENTS):
        x = i * (sw + 1)
        top = 2
        t.fill(x, top, sw, 11, _h(bg), radius=10)
        t.border(
            x,
            top,
            sw,
            11,
            blend(accent, bg, 0.5) if i == 0 else blend("#ffffff", bg, 0.12),
            radius=10,
        )
        t.text(x + 2, top + 1, name.upper(), blend("#ffffff", bg, 0.55), bold=True)
        # mini rows
        t.fill(x + 1, top + 3, sw - 2, 1, blend(accent, bg, 0.22), radius=4)
        t.bar(x + 1, top + 3, 1, accent)
        t.text(x + 2, top + 3, "api-key", blend("#ffffff", bg, 0.92))
        t.text(x + 2, top + 5, "db-password", blend("#ffffff", bg, 0.85))
        t.text(x + 2, top + 6, "token", blend("#ffffff", bg, 0.85))
        t.border(x + 2, top + 8, sw - 5, 1.6, blend(accent, bg, 0.5), radius=5)
        t.text(x + 3, top + 8.3, "sk_live_…b91d", accent)
    return t.save("05-themes.png")


if __name__ == "__main__":
    print(f"font: {FONT_NAME}")
    for fn in (main_browser, login, permissions, confirm, themes):
        print("wrote", os.path.relpath(fn(), HERE))
