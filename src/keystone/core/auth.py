"""Authentication & workspace discovery.

All functions here are blocking (they may open a browser for OAuth U2M); the UI
calls them from worker threads. They lean on the Databricks SDK's unified auth:

  * Workspace URL + OAuth U2M  -> Config(host=..., auth_type="external-browser")
  * Account discovery          -> AccountClient(host=accounts.*, account_id, U2M)
                                  -> workspaces.list() -> get_workspace_client()
"""

from __future__ import annotations

import configparser

from .config import config_path
from .gateway import DatabricksGateway
from .models import AccountWorkspace, Cloud, cloud_by_key


class AuthError(Exception):
    """Login/discovery failure with a UI-friendly message."""


def normalize_host(host: str) -> str:
    host = (host or "").strip()
    if not host:
        raise AuthError("Workspace URL is required.")
    if not host.startswith(("http://", "https://")):
        host = "https://" + host
    return host.rstrip("/")


# ── workspace URL + browser login (US: paste a URL) ────────────────────────
def login_workspace(host: str) -> tuple[DatabricksGateway, str]:
    """OAuth U2M against a single workspace. Returns (gateway, label)."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config

    host = normalize_host(host)
    try:
        cfg = Config(host=host, auth_type="external-browser")
        client = WorkspaceClient(config=cfg)
        me = client.current_user.me()  # triggers the browser flow
    except Exception as exc:  # noqa: BLE001
        raise AuthError(_short(exc)) from exc
    label = f"{me.user_name or 'me'} · {_host_label(host)}"
    return DatabricksGateway.from_client(client), label


# ── account-level discovery (US: go to the account) ────────────────────────
def discover_account(cloud_key: str, account_id: str):
    """Authenticate at the account level and list every workspace.

    Returns (account_client, [AccountWorkspace]). The account_client is kept so
    we can later mint a workspace client for the chosen workspace, reusing the
    same OAuth session.
    """
    from databricks.sdk import AccountClient
    from databricks.sdk.core import Config

    cloud: Cloud = cloud_by_key(cloud_key)
    account_id = (account_id or "").strip()
    if not account_id:
        raise AuthError("Account ID is required.")
    try:
        cfg = Config(
            host=cloud.account_host,
            account_id=account_id,
            auth_type="external-browser",
        )
        account = AccountClient(config=cfg)
        workspaces = []
        for w in account.workspaces.list():
            status = getattr(w.workspace_status, "value", None) or str(
                w.workspace_status or ""
            )
            workspaces.append(
                AccountWorkspace(
                    workspace_id=w.workspace_id or 0,
                    name=w.workspace_name or w.deployment_name or "(unnamed)",
                    deployment_name=w.deployment_name or "",
                    status=status,
                    cloud=cloud.key,
                    raw=w,
                )
            )
    except Exception as exc:  # noqa: BLE001
        raise AuthError(_short(exc)) from exc
    workspaces.sort(key=lambda w: w.name.lower())
    return account, workspaces


def connect_account_workspace(
    account, ws: AccountWorkspace
) -> tuple[DatabricksGateway, str]:
    """Mint a workspace client from the account session for the chosen workspace."""
    try:
        client = account.get_workspace_client(ws.raw)
    except Exception as exc:  # noqa: BLE001
        raise AuthError(_short(exc)) from exc
    return DatabricksGateway.from_client(client), f"{ws.name} · {ws.cloud}"


# ── persistence (mirrors `databricks auth login`) ──────────────────────────
def save_profile(
    name: str,
    host: str,
    account_id: str | None = None,
    auth_type: str = "external-browser",
) -> None:
    """Write a reusable profile into ~/.databrickscfg so next launch is instant.

    For U2M logins we persist host + auth_type (no secret); the OAuth token cache
    handles the rest, exactly like the Databricks CLI does.
    """
    path = config_path()
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path)
    name = name.strip() or "keystone"
    if name != parser.default_section and not parser.has_section(name):
        parser.add_section(name)
    parser.set(name, "host", normalize_host(host))
    parser.set(name, "auth_type", auth_type)
    if account_id:
        parser.set(name, "account_id", account_id.strip())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        parser.write(fh)


def _host_label(host: str) -> str:
    return host.replace("https://", "").replace("http://", "").rstrip("/")


def _short(exc: Exception) -> str:
    msg = str(exc).strip().splitlines()
    return msg[0] if msg else exc.__class__.__name__
