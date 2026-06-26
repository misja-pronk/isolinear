"""The Databricks boundary.

`Gateway` is the port the rest of the app depends on; `DatabricksGateway` is the
concrete adapter over the Databricks SDK. Tests substitute any object satisfying
the `Gateway` protocol (see tests/fakes.py), so nothing above this layer ever
imports the SDK.

All methods are blocking; the UI calls them from worker threads. Adapters convert
SDK types into our own plain models (see models.py).
"""

from __future__ import annotations

import base64
from typing import Protocol, runtime_checkable

from .models import Acl, Identity, Scope, Secret


class GatewayError(Exception):
    """Raised when a Databricks operation fails; carries a UI-friendly message."""


@runtime_checkable
class Gateway(Protocol):
    """Port: everything the app needs from a Databricks workspace."""

    profile: str | None

    def whoami(self) -> Identity: ...
    def list_scopes(self) -> list[Scope]: ...
    def create_scope(self, name: str) -> None: ...
    def delete_scope(self, name: str) -> None: ...
    def list_secrets(self, scope: str) -> list[Secret]: ...
    def get_secret_value(self, scope: str, key: str) -> str: ...
    def put_secret(self, scope: str, key: str, value: str) -> None: ...
    def delete_secret(self, scope: str, key: str) -> None: ...
    def list_acls(self, scope: str) -> list[Acl]: ...
    def put_acl(self, scope: str, principal: str, permission: str) -> None: ...
    def delete_acl(self, scope: str, principal: str) -> None: ...


class DatabricksGateway:
    """Adapter: a `Gateway` backed by a Databricks `WorkspaceClient`.

    Two ways in:
      * from_profile(name) — connect via a ~/.databrickscfg profile (lazy).
      * from_client(client) — wrap an already-authenticated client, e.g. one
        produced by an OAuth browser login or AccountClient.get_workspace_client.
    """

    def __init__(self, *, profile: str | None = None, client=None) -> None:
        self.profile = profile
        self._client = client  # may be pre-built (OAuth/account) or lazy (profile)

    @classmethod
    def from_profile(cls, profile: str) -> DatabricksGateway:
        return cls(profile=profile)

    @classmethod
    def from_client(cls, client) -> DatabricksGateway:
        return cls(client=client)

    # -- connection ---------------------------------------------------------
    @property
    def client(self):
        if self._client is None:
            # Imported lazily so the app starts fast and offline-friendly.
            from databricks.sdk import WorkspaceClient

            self._client = WorkspaceClient(profile=self.profile)
        return self._client

    def whoami(self) -> Identity:
        try:
            me = self.client.current_user.me()
            return Identity(
                user_name=me.user_name or "",
                display_name=getattr(me, "display_name", "") or me.user_name or "",
                authenticated=True,
            )
        except Exception as exc:  # noqa: BLE001 - surface any auth/connectivity issue
            return Identity(authenticated=False, error=_short(exc))

    # -- scopes -------------------------------------------------------------
    def list_scopes(self) -> list[Scope]:
        try:
            out: list[Scope] = []
            for s in self.client.secrets.list_scopes():
                backend = getattr(s.backend_type, "value", None) or str(
                    s.backend_type or "DATABRICKS"
                )
                out.append(Scope(name=s.name or "", backend_type=backend))
            return sorted(out, key=lambda s: s.name.lower())
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    def create_scope(self, name: str) -> None:
        try:
            self.client.secrets.create_scope(scope=name)
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    def delete_scope(self, name: str) -> None:
        try:
            self.client.secrets.delete_scope(scope=name)
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    # -- secrets ------------------------------------------------------------
    def list_secrets(self, scope: str) -> list[Secret]:
        try:
            out: list[Secret] = []
            for m in self.client.secrets.list_secrets(scope=scope):
                out.append(
                    Secret(
                        scope=scope,
                        key=m.key or "",
                        last_updated_ms=m.last_updated_timestamp,
                    )
                )
            return sorted(out, key=lambda s: s.key.lower())
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    def get_secret_value(self, scope: str, key: str) -> str:
        try:
            resp = self.client.secrets.get_secret(scope=scope, key=key)
            raw = resp.value or ""
            try:
                return base64.b64decode(raw).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                # Binary or non-utf8 secret — show the base64 form.
                return raw
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    def put_secret(self, scope: str, key: str, value: str) -> None:
        try:
            self.client.secrets.put_secret(scope=scope, key=key, string_value=value)
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    def delete_secret(self, scope: str, key: str) -> None:
        try:
            self.client.secrets.delete_secret(scope=scope, key=key)
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    # -- acls ---------------------------------------------------------------
    def list_acls(self, scope: str) -> list[Acl]:
        try:
            out: list[Acl] = []
            for a in self.client.secrets.list_acls(scope=scope):
                perm = getattr(a.permission, "value", None) or str(a.permission or "")
                out.append(Acl(principal=a.principal or "", permission=perm))
            return sorted(out, key=lambda a: a.principal.lower())
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    def put_acl(self, scope: str, principal: str, permission: str) -> None:
        from databricks.sdk.service.workspace import AclPermission

        try:
            self.client.secrets.put_acl(
                scope=scope, principal=principal, permission=AclPermission(permission)
            )
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc

    def delete_acl(self, scope: str, principal: str) -> None:
        try:
            self.client.secrets.delete_acl(scope=scope, principal=principal)
        except Exception as exc:  # noqa: BLE001
            raise GatewayError(_short(exc)) from exc


def _short(exc: Exception) -> str:
    """Condense an SDK exception into a single readable line."""
    msg = str(exc).strip().splitlines()
    return msg[0] if msg else exc.__class__.__name__
