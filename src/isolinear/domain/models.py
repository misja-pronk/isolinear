"""Domain model — the ubiquitous language of Isolinear as plain value objects.

No Textual, no Databricks SDK, no I/O. These are the nouns the whole app speaks:
workspaces, scopes, secrets, ACLs, identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class Workspace:
    """A connection target — one profile from ~/.databrickscfg."""

    profile: str
    host: str

    @property
    def label(self) -> str:
        host = self.host.replace("https://", "").replace("http://", "").rstrip("/")
        return f"{self.profile}  ·  {host}" if host else self.profile


@dataclass(frozen=True)
class Cloud:
    key: str  # aws | azure | gcp
    label: str
    account_host: str


CLOUDS: list[Cloud] = [
    Cloud("aws", "AWS", "https://accounts.cloud.databricks.com"),
    Cloud("azure", "Azure", "https://accounts.azuredatabricks.net"),
    Cloud("gcp", "GCP", "https://accounts.gcp.databricks.com"),
]


def cloud_by_key(key: str) -> Cloud:
    return next(c for c in CLOUDS if c.key == key)


@dataclass
class AccountWorkspace:
    """A workspace discovered via the account-level API (US-1, discovery)."""

    workspace_id: int
    name: str
    deployment_name: str = ""
    status: str = ""
    cloud: str = ""
    raw: object = None  # original SDK provisioning.Workspace, for get_workspace_client

    @property
    def label(self) -> str:
        status = f"  ·  {self.status}" if self.status else ""
        return f"{self.name}  ·  id {self.workspace_id}{status}"


@dataclass
class Scope:
    name: str
    backend_type: str = "DATABRICKS"

    @property
    def is_keyvault(self) -> bool:
        return self.backend_type == "AZURE_KEYVAULT"

    @property
    def icon(self) -> str:
        return "☁" if self.is_keyvault else "🔒"


@dataclass
class Secret:
    scope: str
    key: str
    last_updated_ms: int | None = None

    @property
    def last_updated(self) -> str:
        if not self.last_updated_ms:
            return "—"
        dt = datetime.fromtimestamp(self.last_updated_ms / 1000, tz=UTC)
        return dt.strftime("%Y-%m-%d %H:%M")


@dataclass
class Acl:
    principal: str
    permission: str  # READ | WRITE | MANAGE


@dataclass
class Identity:
    """Who we are authenticated as in a workspace."""

    user_name: str = ""
    display_name: str = ""
    authenticated: bool = False
    error: str = ""
