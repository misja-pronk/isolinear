from __future__ import annotations

from fakes import FakeGateway, seeded_gateway
from keystone.core import Scope, WorkspaceSession


def test_authenticate_and_load_scopes_populate_cache():
    gw = seeded_gateway()
    s = WorkspaceSession(gw, "t")
    assert s.authenticate().authenticated
    assert [sc.name for sc in s.load_scopes()] == ["kv", "prod"]
    assert s.scopes  # cached


def test_warm_scope_pulls_secrets_and_acls():
    s = WorkspaceSession(seeded_gateway(), "t")
    s.load_scopes()
    s.warm_scope("prod")
    assert {sec.key for sec in s.secrets_for("prod")} == {"api-key", "db-password"}
    assert any(a.permission == "MANAGE" for a in s.acls_for("prod"))


def test_warm_scope_swallows_gateway_errors():
    gw = FakeGateway(scopes=[Scope("prod")], fail_on={"list_secrets"})
    s = WorkspaceSession(gw, "t")
    s.load_scopes()
    s.warm_scope("prod")  # must not raise
    assert s.secrets_for("prod") == []


def test_reveal_caches_value(session: WorkspaceSession):
    gw: FakeGateway = session._gateway  # type: ignore[attr-defined]
    first = session.reveal("prod", "api-key")
    second = session.reveal("prod", "api-key")
    assert first == second
    assert gw.count("get_secret_value") == 1  # fetched once, then cached


def test_put_secret_updates_cache_and_value():
    s = WorkspaceSession(seeded_gateway(), "t")
    s.load_scopes()
    s.warm_scope("prod")
    s.put_secret("prod", "new-key", "v")
    assert any(sec.key == "new-key" for sec in s.secrets_for("prod"))
    assert s.cached_value("prod", "new-key") == "v"


def test_delete_secret_and_scope(session: WorkspaceSession):
    session.delete_secret("prod", "api-key")
    assert all(sec.key != "api-key" for sec in session.secrets_for("prod"))
    session.delete_scope("kv")
    assert all(sc.name != "kv" for sc in session.scopes)


def test_create_scope(session: WorkspaceSession):
    session.create_scope("staging")
    assert any(sc.name == "staging" for sc in session.scopes)


def test_auth_summary_delegates(session: WorkspaceSession):
    session.authenticate()
    summary = {s.scope: s for s in session.auth_summary()}
    assert summary["prod"].can_manage


def test_set_acl_grants_permission(session: WorkspaceSession):
    session.set_acl("kv", "newbie@corp.com", "WRITE")
    perms = {a.principal: a.permission for a in session.acls_for("kv")}
    assert perms["newbie@corp.com"] == "WRITE"


def test_set_acl_is_an_upsert(session: WorkspaceSession):
    session.set_acl("prod", "me@corp.com", "READ")  # was MANAGE
    perms = {a.principal: a.permission for a in session.acls_for("prod")}
    assert perms["me@corp.com"] == "READ"
    # auth summary reflects the downgrade
    session.authenticate()
    summary = {s.scope: s for s in session.auth_summary()}
    assert not summary["prod"].can_manage


def test_remove_acl(session: WorkspaceSession):
    session.remove_acl("prod", "users")
    assert all(a.principal != "users" for a in session.acls_for("prod"))
