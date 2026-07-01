"""Authorization rules — a domain service.

The "what can this principal do" logic that used to live on the cache. It's a
business rule about scopes + ACLs + identity, so it belongs in the domain.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import Acl, Identity, Scope

_PERM_RANK = {"READ": 1, "WRITE": 2, "MANAGE": 3}


def perm_rank(permission: str) -> int:
    return _PERM_RANK.get(permission, 0)


@dataclass
class AuthSummary:
    """Per-scope authorization picture for the authorization overview screen."""

    scope: str
    effective: str = "—"  # current user's effective permission
    acl_count: int = 0
    can_write: bool = False
    can_manage: bool = False


def authorization_summary(
    identity: Identity,
    scopes: list[Scope],
    acls_by_scope: Mapping[str, list[Acl]],
) -> list[AuthSummary]:
    """Compute the current user's effective permission on each scope (US-13).

    "Effective" is the highest permission granted to any principal that is *you*:
    your username, the `users` group (everyone), or any group you belong to — so
    group-based access (the common case) counts, not just direct user ACLs.
    """
    mine = {identity.user_name, "users"} | set(identity.groups)
    summaries: list[AuthSummary] = []
    for scope in scopes:
        acls = acls_by_scope.get(scope.name, [])
        effective = "—"
        best = 0
        for acl in acls:
            if acl.principal in mine and perm_rank(acl.permission) > best:
                best = perm_rank(acl.permission)
                effective = acl.permission
        summaries.append(
            AuthSummary(
                scope=scope.name,
                effective=effective,
                acl_count=len(acls),
                can_write=best >= perm_rank("WRITE"),
                can_manage=best >= perm_rank("MANAGE"),
            )
        )
    return summaries
