"""DatabricksConnector — the infrastructure adapter for login.

Implements the domain's `WorkspaceConnector` over the Databricks SDK's unified
auth:

  * connect_profile -> a named ~/.databrickscfg profile
  * connect_url     -> Config(host=..., auth_type="external-browser") U2M (OAuth)

Both block (connect_url may open a browser); callers run them in worker threads.
"""

from __future__ import annotations

from ..domain import Connected, normalize_host
from ..domain.errors import AuthError
from .databricks import DatabricksSecretStore


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


def _host_label(host: str) -> str:
    return host.replace("https://", "").replace("http://", "").rstrip("/")


def _short(exc: Exception) -> str:
    msg = str(exc).strip().splitlines()
    return msg[0] if msg else exc.__class__.__name__
