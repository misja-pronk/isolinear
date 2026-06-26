from __future__ import annotations

from keystone.core import Acl, Identity, Scope, Secret, WorkspaceCache


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


def test_auth_summary_computes_effective_permission():
    cache = WorkspaceCache(label="t")
    cache.identity = Identity("me@corp.com", authenticated=True)
    cache.scopes = [Scope("prod"), Scope("ro")]
    cache.acls = {
        "prod": [Acl("me@corp.com", "MANAGE"), Acl("users", "READ")],
        "ro": [Acl("users", "READ")],  # matched via the 'users' group
    }
    summaries = {s.scope: s for s in cache.auth_summary()}
    assert summaries["prod"].effective == "MANAGE"
    assert summaries["prod"].can_write and summaries["prod"].can_manage
    assert summaries["ro"].effective == "READ"
    assert not summaries["ro"].can_write
