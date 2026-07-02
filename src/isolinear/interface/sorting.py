"""Shared sort bookkeeping for every sortable table in the UI.

One interaction model everywhere: `s` advances to the next column (ascending),
`S` reverses the direction, and clicking a header toggles that column. The
active column is marked with a ↑ / ↓ in its label.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

Row = TypeVar("Row")


class SortState:
    """Sort state for one table.

    `count` is the number of *sortable* columns — a table may display more
    (e.g. the audit's Updated and Age both sort by the same timestamp key).
    `col=None` is natural order; only the login picker starts there.
    """

    def __init__(self, count: int, col: int | None = 0, rev: bool = False) -> None:
        self._count = count
        self.col = col
        self.rev = rev

    def cycle(self) -> None:
        """`s`: advance to the next column, ascending."""
        self.col = 0 if self.col is None else (self.col + 1) % self._count
        self.rev = False

    def flip(self) -> None:
        """`S`: reverse the current direction."""
        if self.col is None:
            self.col = 0
        self.rev = not self.rev

    def click(self, col: int) -> None:
        """Header click: same column toggles direction, a new one sorts ascending."""
        col = min(col, self._count - 1)
        if col == self.col:
            self.rev = not self.rev
        else:
            self.col, self.rev = col, False

    def labels(self, names: Sequence[str]) -> list[str]:
        """Column labels with a ↑ / ↓ marking the active sort column."""
        arrow = "↓" if self.rev else "↑"
        return [f"{n} {arrow}" if i == self.col else n for i, n in enumerate(names)]

    def apply(
        self, rows: Sequence[Row], keys: Sequence[Callable[[Row], Any]]
    ) -> list[Row]:
        """Rows sorted by the active column's key (natural order when unsorted)."""
        if self.col is None:
            return list(rows)
        return sorted(rows, key=keys[self.col], reverse=self.rev)
