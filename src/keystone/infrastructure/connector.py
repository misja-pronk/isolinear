"""DatabricksConnector — the infrastructure adapter for login & discovery.

Implements the domain's `WorkspaceConnector` / `AccountSession` ports over the
Databricks SDK's unified auth:

  * connect_url    -> Config(host=..., auth_type="external-browser") U2M
  * discover_account -> AccountClient(host=accounts.*, account_id, U2M)
                        -> workspaces.list() -> get_workspace_client()

All methods block (they may open a browser); callers run them in worker threads.
"""

from __future__ import annotations

from ..domain import AccountWorkspace, Connected, cloud_by_key, normalize_host
from ..domain.errors import AuthError
from .databricks import DatabricksSecretStore


class DatabricksAccountSession:
    """A live account session (`AccountSession` port) wrapping an AccountClient."""

    def __init__(self, account, workspaces: list[AccountWorkspace]) -> None:
        self._account = account
        self._workspaces = workspaces

    @property
    def workspaces(self) -> list[AccountWorkspace]:
        return self._workspaces

    def connect(self, ws: AccountWorkspace) -> Connected:
        try:
            client = self._account.get_workspace_client(ws.raw)
        except Exception as exc:  # noqa: BLE001
            raise AuthError(_short(exc)) from exc
        return Connected(
            DatabricksSecretStore.from_client(client),
            f"{ws.name} · {ws.cloud}",
            _client_host(client),
        )


class DatabricksConnector:
    """A `WorkspaceConnector` backed by the Databricks SDK."""

    def connect_profile(self, profile: str) -> Connected:
        return Connected(DatabricksSecretStore.from_profile(profile), profile)

    def connect_url(self, host: str) -> Connected:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config

        host = normalize_host(host)
        try:
            client = WorkspaceClient(
                config=Config(host=host, auth_type="external-browser")
            )
            me = client.current_user.me()  # triggers the browser flow
        except Exception as exc:  # noqa: BLE001
            raise AuthError(_short(exc)) from exc
        label = f"{me.user_name or 'me'} · {_host_label(host)}"
        return Connected(DatabricksSecretStore.from_client(client), label, host)

    def discover_account(
        self, cloud_key: str, account_id: str
    ) -> DatabricksAccountSession:
        from databricks.sdk import AccountClient
        from databricks.sdk.core import Config

        cloud = cloud_by_key(cloud_key)
        account_id = (account_id or "").strip()
        if not account_id:
            raise AuthError("Account ID is required.")
        try:
            account = AccountClient(
                config=Config(
                    host=cloud.account_host,
                    account_id=account_id,
                    auth_type="external-browser",
                )
            )
            workspaces = [
                AccountWorkspace(
                    workspace_id=w.workspace_id or 0,
                    name=w.workspace_name or w.deployment_name or "(unnamed)",
                    deployment_name=w.deployment_name or "",
                    status=getattr(w.workspace_status, "value", None)
                    or str(w.workspace_status or ""),
                    cloud=cloud.key,
                    raw=w,
                )
                for w in account.workspaces.list()
            ]
        except Exception as exc:  # noqa: BLE001
            raise AuthError(_short(exc)) from exc
        workspaces.sort(key=lambda w: w.name.lower())
        return DatabricksAccountSession(account, workspaces)


def _client_host(client) -> str:
    try:
        return client.config.host or ""
    except Exception:  # noqa: BLE001
        return ""


def _host_label(host: str) -> str:
    return host.replace("https://", "").replace("http://", "").rstrip("/")


def _short(exc: Exception) -> str:
    msg = str(exc).strip().splitlines()
    return msg[0] if msg else exc.__class__.__name__
