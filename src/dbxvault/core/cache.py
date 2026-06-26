"""In-memory cache that pre-loads a workspace for an instant browsing experience.

Strategy (US-14/16):
  * On connect we warm scopes -> secrets metadata -> ACLs in the background.
  * Secret *values* are NOT bulk-loaded; they are fetched lazily on reveal and
    cached thereafter, so sensitive material isn't pulled into memory needlessly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Acl, AuthSummary, Identity, Scope, Secret, perm_rank


@dataclass
class WorkspaceCache:
    label: str
    identity: Identity = field(default_factory=Identity)

    scopes: list[Scope] = field(default_factory=list)
    secrets: dict[str, list[Secret]] = field(default_factory=dict)
    acls: dict[str, list[Acl]] = field(default_factory=dict)
    values: dict[tuple[str, str], str] = field(default_factory=dict)

    scopes_loaded: bool = False
    warm_error: str = ""

    # -- lookups ------------------------------------------------------------
    def secrets_for(self, scope: str) -> list[Secret]:
        return self.secrets.get(scope, [])

    def acls_for(self, scope: str) -> list[Acl]:
        return self.acls.get(scope, [])

    def cached_value(self, scope: str, key: str) -> str | None:
        return self.values.get((scope, key))

    def set_value(self, scope: str, key: str, value: str) -> None:
        self.values[(scope, key)] = value

    # -- mutation keeping cache + UI consistent -----------------------------
    def upsert_secret(self, secret: Secret) -> None:
        rows = self.secrets.setdefault(secret.scope, [])
        for i, existing in enumerate(rows):
            if existing.key == secret.key:
                rows[i] = secret
                break
        else:
            rows.append(secret)
        rows.sort(key=lambda s: s.key.lower())

    def remove_secret(self, scope: str, key: str) -> None:
        self.secrets[scope] = [s for s in self.secrets.get(scope, []) if s.key != key]
        self.values.pop((scope, key), None)

    def add_scope(self, scope: Scope) -> None:
        if not any(s.name == scope.name for s in self.scopes):
            self.scopes.append(scope)
            self.scopes.sort(key=lambda s: s.name.lower())
        self.secrets.setdefault(scope.name, [])
        self.acls.setdefault(scope.name, [])

    def remove_scope(self, name: str) -> None:
        self.scopes = [s for s in self.scopes if s.name != name]
        self.secrets.pop(name, None)
        self.acls.pop(name, None)
        self.values = {k: v for k, v in self.values.items() if k[0] != name}

    # -- authorization overview (US-13) -------------------------------------
    def auth_summary(self) -> list[AuthSummary]:
        me = self.identity.user_name
        summaries: list[AuthSummary] = []
        for scope in self.scopes:
            acls = self.acls.get(scope.name, [])
            effective = "—"
            best = 0
            for acl in acls:
                is_mine = acl.principal in (me, "users", "admins")
                if is_mine and perm_rank(acl.permission) > best:
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
