"""In-memory test doubles for the domain ports — faithful stand-ins for
Databricks. They implement the `SecretStore`, `WorkspaceConnector`, and
`ProfileStore` protocols so the whole stack above infrastructure is testable
without a network.
"""

from __future__ import annotations

from isolinear.application import OnboardingService
from isolinear.domain import Acl, Identity, Scope, Secret
from isolinear.domain.errors import StoreError


class FakeSecretStore:
    def __init__(
        self,
        *,
        profile: str | None = "fake",
        scopes: list[Scope] | None = None,
        secrets: dict[str, list[Secret]] | None = None,
        acls: dict[str, list[Acl]] | None = None,
        values: dict[tuple[str, str], str] | None = None,
        identity: Identity | None = None,
        fail_on: set[str] | None = None,
    ) -> None:
        self.profile = profile
        self._scopes = scopes or []
        self._secrets = secrets or {}
        self._acls = acls or {}
        self._values = values or {}
        self._identity = identity or Identity("me@corp.com", "Me", authenticated=True)
        self._fail_on = fail_on or set()
        self.calls: list[tuple] = []

    def _record(self, *call) -> None:
        self.calls.append(call)
        if call[0] in self._fail_on:
            raise StoreError(f"boom:{call[0]}")

    def count(self, name: str) -> int:
        return sum(1 for c in self.calls if c[0] == name)

    # -- Gateway protocol ----------------------------------------------
    def whoami(self) -> Identity:
        self.calls.append(("whoami",))
        return self._identity

    def list_scopes(self) -> list[Scope]:
        self._record("list_scopes")
        # mirror DatabricksSecretStore's observable contract: sorted results
        return sorted(self._scopes, key=lambda s: s.name.lower())

    def create_scope(self, name: str) -> None:
        self._record("create_scope", name)
        self._scopes.append(Scope(name=name))
        self._secrets.setdefault(name, [])
        self._acls.setdefault(name, [])

    def delete_scope(self, name: str) -> None:
        self._record("delete_scope", name)
        self._scopes = [s for s in self._scopes if s.name != name]
        self._secrets.pop(name, None)

    def list_secrets(self, scope: str) -> list[Secret]:
        self._record("list_secrets", scope)
        return sorted(self._secrets.get(scope, []), key=lambda s: s.key.lower())

    def get_secret_value(self, scope: str, key: str) -> str:
        self._record("get_secret_value", scope, key)
        return self._values.get((scope, key), f"value::{scope}/{key}")

    def put_secret(self, scope: str, key: str, value: str) -> None:
        self._record("put_secret", scope, key, value)
        self._values[(scope, key)] = value
        rows = self._secrets.setdefault(scope, [])
        if not any(s.key == key for s in rows):
            rows.append(Secret(scope=scope, key=key))

    def delete_secret(self, scope: str, key: str) -> None:
        self._record("delete_secret", scope, key)
        self._secrets[scope] = [s for s in self._secrets.get(scope, []) if s.key != key]

    def list_acls(self, scope: str) -> list[Acl]:
        self._record("list_acls", scope)
        return sorted(self._acls.get(scope, []), key=lambda a: a.principal.lower())

    def put_acl(self, scope: str, principal: str, permission: str) -> None:
        self._record("put_acl", scope, principal, permission)
        rows = [a for a in self._acls.get(scope, []) if a.principal != principal]
        rows.append(Acl(principal=principal, permission=permission))
        self._acls[scope] = rows

    def delete_acl(self, scope: str, principal: str) -> None:
        self._record("delete_acl", scope, principal)
        self._acls[scope] = [
            a for a in self._acls.get(scope, []) if a.principal != principal
        ]


def seeded_store() -> FakeSecretStore:
    """A standard two-scope dataset used across UI/session tests."""
    return FakeSecretStore(
        scopes=[Scope("prod", "DATABRICKS"), Scope("kv", "AZURE_KEYVAULT")],
        secrets={
            "prod": [
                Secret("prod", "api-key", 1_718_000_000_000),
                Secret("prod", "db-password", 1_718_500_000_000),
            ],
            "kv": [Secret("kv", "tenant-id", 1_717_000_000_000)],
        },
        acls={
            "prod": [Acl("me@corp.com", "MANAGE"), Acl("users", "READ")],
            "kv": [Acl("users", "READ")],
        },
    )


class StubProfiles:
    """A `ProfileStore` that holds profiles in memory."""

    def __init__(self, workspaces=None) -> None:
        self._workspaces = list(workspaces or [])
        self.saved: list[tuple] = []

    def discover(self):
        return list(self._workspaces)

    def save(self, name, host, account_id=None) -> None:
        self.saved.append((name, host, account_id))


class StubConnector:
    """A `WorkspaceConnector` that refuses to connect (login needs a network)."""

    def connect_profile(self, profile):
        raise NotImplementedError

    def connect_url(self, host):
        raise NotImplementedError


class StubBundle:
    """A `BundleStore` that returns a preset bundle workspace (or none)."""

    def __init__(self, workspace=None) -> None:
        self._workspace = workspace

    def discover(self):
        return self._workspace


def stub_onboarding(profiles=None, bundle=None) -> OnboardingService:
    """An OnboardingService wired to stubs — listed workspaces, no live connect."""
    return OnboardingService(StubConnector(), StubProfiles(profiles), StubBundle(bundle))
