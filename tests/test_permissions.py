from __future__ import annotations

from isolinear.domain import Acl, Identity, Scope, perm_rank
from isolinear.domain.permissions import authorization_summary


def test_perm_rank_orders_permissions():
    assert perm_rank("READ") < perm_rank("WRITE") < perm_rank("MANAGE")
    assert perm_rank("nonsense") == 0


def test_authorization_summary_computes_effective_permission():
    identity = Identity("me@corp.com", authenticated=True)
    scopes = [Scope("prod"), Scope("ro")]
    acls = {
        "prod": [Acl("me@corp.com", "MANAGE"), Acl("users", "READ")],
        "ro": [Acl("users", "READ")],  # matched via the 'users' group
    }
    summaries = {s.scope: s for s in authorization_summary(identity, scopes, acls)}
    assert summaries["prod"].effective == "MANAGE"
    assert summaries["prod"].can_write and summaries["prod"].can_manage
    assert summaries["ro"].effective == "READ"
    assert not summaries["ro"].can_write


def test_effective_permission_resolves_via_group_membership():
    # no direct ACL on 'shared', but you belong to 'data-engineers' which has WRITE
    identity = Identity("me@corp.com", authenticated=True, groups=["data-engineers"])
    scopes = [Scope("shared"), Scope("other")]
    acls = {
        "shared": [Acl("data-engineers", "WRITE"), Acl("admins", "MANAGE")],
        "other": [Acl("platform-team", "MANAGE")],  # a group you're NOT in
    }
    summaries = {s.scope: s for s in authorization_summary(identity, scopes, acls)}
    # your group grants WRITE; the admins ACL does NOT apply (you're not an admin)
    assert summaries["shared"].effective == "WRITE"
    assert summaries["shared"].can_write and not summaries["shared"].can_manage
    # a group you don't belong to grants you nothing
    assert summaries["other"].effective == "—"


def test_readable_scope_floors_effective_to_read():
    # you can list 'shared' secrets (READ) but its ACLs are off-limits (needs
    # MANAGE), so no grant looks like yours — access must still read as READ,
    # not "none". 'hidden' isn't readable at all, so it stays "none".
    identity = Identity("me@corp.com", authenticated=True)
    scopes = [Scope("shared"), Scope("hidden")]
    summaries = {
        s.scope: s
        for s in authorization_summary(identity, scopes, {}, readable={"shared"})
    }
    assert summaries["shared"].effective == "READ"
    assert not summaries["shared"].can_write
    assert summaries["hidden"].effective == "—"


def test_visible_manage_grant_beats_readable_floor():
    # a visible MANAGE grant wins over the READ floor for a readable scope
    identity = Identity("me@corp.com", authenticated=True, groups=["admins"])
    scopes = [Scope("shared")]
    acls = {"shared": [Acl("admins", "MANAGE")]}
    summaries = {
        s.scope: s
        for s in authorization_summary(identity, scopes, acls, readable={"shared"})
    }
    assert summaries["shared"].effective == "MANAGE"
    assert summaries["shared"].can_manage
