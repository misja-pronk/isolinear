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
