"""SortState — the shared sort bookkeeping used by every sortable table."""

from __future__ import annotations

from isolinear.interface.sorting import SortState

KEYS = (lambda r: r[0], lambda r: r[1])
ROWS = [("b", 2), ("a", 3), ("c", 1)]


def test_cycle_advances_columns_ascending():
    s = SortState(2)
    assert s.apply(ROWS, KEYS) == [("a", 3), ("b", 2), ("c", 1)]
    s.cycle()  # -> col 1 ascending
    assert (s.col, s.rev) == (1, False)
    assert s.apply(ROWS, KEYS) == [("c", 1), ("b", 2), ("a", 3)]
    s.cycle()  # wraps back to col 0
    assert (s.col, s.rev) == (0, False)


def test_flip_reverses_and_click_toggles():
    s = SortState(2)
    s.flip()
    assert s.apply(ROWS, KEYS) == [("c", 1), ("b", 2), ("a", 3)]
    s.click(0)  # same column -> toggle back to ascending
    assert (s.col, s.rev) == (0, False)
    s.click(1)  # new column -> ascending
    assert (s.col, s.rev) == (1, False)
    s.click(5)  # clamped to the last sortable column
    assert s.col == 1 and s.rev is True


def test_unsorted_natural_order_until_first_sort():
    s = SortState(3, col=None)
    assert s.apply(ROWS, KEYS) == ROWS  # natural order preserved
    assert s.labels(("A", "B", "C")) == ["A", "B", "C"]  # no arrow anywhere
    s.cycle()
    assert (s.col, s.rev) == (0, False)


def test_labels_mark_only_the_active_column():
    s = SortState(2, col=1, rev=True)
    assert s.labels(("Principal", "Access")) == ["Principal", "Access ↓"]
    s.flip()
    assert s.labels(("Principal", "Access")) == ["Principal", "Access ↑"]
