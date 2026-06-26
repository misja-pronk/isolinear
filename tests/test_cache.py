from __future__ import annotations

from keystone.application import WorkspaceCache
from keystone.domain import Scope, Secret


def test_upsert_secret_adds_updates_and_sorts():
    cache = WorkspaceCache(label="t")
    cache.upsert_secret(Secret("s", "b"))
    cache.upsert_secret(Secret("s", "a"))
    assert [s.key for s in cache.secrets_for("s")] == ["a", "b"]
    # updating an existing key replaces it, not duplicates
    cache.upsert_secret(Secret("s", "a", last_updated_ms=123))
    rows = cache.secrets_for("s")
    assert len(rows) == 2
    assert rows[0].last_updated_ms == 123


def test_remove_secret_drops_row_and_cached_value():
    cache = WorkspaceCache(label="t")
    cache.upsert_secret(Secret("s", "a"))
    cache.set_value("s", "a", "secret")
    cache.remove_secret("s", "a")
    assert cache.secrets_for("s") == []
    assert cache.cached_value("s", "a") is None


def test_add_and_remove_scope():
    cache = WorkspaceCache(label="t")
    cache.add_scope(Scope("s"))
    cache.set_value("s", "k", "v")
    assert any(sc.name == "s" for sc in cache.scopes)
    cache.remove_scope("s")
    assert cache.scopes == []
    assert cache.cached_value("s", "k") is None
