"""WorkspaceSession — the application service.

Owns a `Gateway` + its `WorkspaceCache` and exposes every operation the UI needs
as a plain, synchronous method. All Databricks/cache coordination lives here, so:

  * the UI just calls a method and renders the result (no business logic), and
  * the whole layer is unit-testable with a fake gateway and no event loop.

The UI runs these (blocking) methods in worker threads.
"""

from __future__ import annotations

from collections.abc import Iterator

from .cache import WorkspaceCache
from .gateway import Gateway
from .models import Acl, AuthSummary, Identity, Scope, Secret


class WorkspaceSession:
    def __init__(self, gateway: Gateway, label: str) -> None:
        self._gateway = gateway
        self.cache = WorkspaceCache(label=label)

    @property
    def label(self) -> str:
        return self.cache.label

    @property
    def identity(self) -> Identity:
        return self.cache.identity

    @property
    def scopes(self) -> list[Scope]:
        return self.cache.scopes

    # -- connection / warming -------------------------------------------
    def authenticate(self) -> Identity:
        identity = self._gateway.whoami()
        self.cache.identity = identity
        return identity

    def load_scopes(self) -> list[Scope]:
        scopes = self._gateway.list_scopes()
        self.cache.scopes = scopes
        self.cache.scopes_loaded = True
        return scopes

    def warm_scope(self, scope: str) -> None:
        """Pull secret metadata + ACLs for one scope into the cache."""
        from .gateway import GatewayError

        try:
            self.cache.secrets[scope] = self._gateway.list_secrets(scope)
            self.cache.acls[scope] = self._gateway.list_acls(scope)
        except GatewayError:
            self.cache.secrets.setdefault(scope, [])
            self.cache.acls.setdefault(scope, [])

    def warm_all(self) -> Iterator[tuple[int, int, Scope]]:
        """Warm every scope, yielding (index, total, scope) for progress."""
        total = len(self.cache.scopes)
        for i, scope in enumerate(self.cache.scopes, 1):
            self.warm_scope(scope.name)
            yield i, total, scope

    # -- reads ----------------------------------------------------------
    def secrets_for(self, scope: str) -> list[Secret]:
        return self.cache.secrets_for(scope)

    def acls_for(self, scope: str) -> list[Acl]:
        return self.cache.acls_for(scope)

    def scope(self, name: str) -> Scope | None:
        return next((s for s in self.cache.scopes if s.name == name), None)

    def secret(self, scope: str, key: str) -> Secret | None:
        return next((s for s in self.cache.secrets_for(scope) if s.key == key), None)

    def cached_value(self, scope: str, key: str) -> str | None:
        return self.cache.cached_value(scope, key)

    def reveal(self, scope: str, key: str) -> str:
        """Return the secret value, fetching+caching it on first access."""
        cached = self.cache.cached_value(scope, key)
        if cached is not None:
            return cached
        value = self._gateway.get_secret_value(scope, key)
        self.cache.set_value(scope, key, value)
        return value

    # -- mutations ------------------------------------------------------
    def put_secret(self, scope: str, key: str, value: str) -> None:
        from .gateway import GatewayError

        self._gateway.put_secret(scope, key, value)
        try:  # refresh metadata so the timestamp is accurate
            self.cache.secrets[scope] = self._gateway.list_secrets(scope)
        except GatewayError:
            self.cache.upsert_secret(Secret(scope=scope, key=key))
        self.cache.set_value(scope, key, value)

    def delete_secret(self, scope: str, key: str) -> None:
        self._gateway.delete_secret(scope, key)
        self.cache.remove_secret(scope, key)

    def create_scope(self, name: str) -> None:
        self._gateway.create_scope(name)
        self.cache.add_scope(Scope(name=name))

    def delete_scope(self, name: str) -> None:
        self._gateway.delete_scope(name)
        self.cache.remove_scope(name)

    def refresh_scope(self, scope: str) -> None:
        self.warm_scope(scope)

    # -- scope permissions / ACLs (US-11 update, US-12) -----------------
    def set_acl(self, scope: str, principal: str, permission: str) -> None:
        """Grant or change a principal's permission (put_acl is an upsert)."""
        self._gateway.put_acl(scope, principal, permission)
        self.cache.acls[scope] = self._gateway.list_acls(scope)

    def remove_acl(self, scope: str, principal: str) -> None:
        self._gateway.delete_acl(scope, principal)
        self.cache.acls[scope] = self._gateway.list_acls(scope)

    # -- authorization overview ----------------------------------------
    def auth_summary(self) -> list[AuthSummary]:
        return self.cache.auth_summary()
