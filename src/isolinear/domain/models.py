"""Domain model — the ubiquitous language of Isolinear as plain value objects.

No Textual, no Databricks SDK, no I/O. These are the nouns the whole app speaks:
workspaces, scopes, secrets, ACLs, identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

# Where a connection target was discovered. Shown to the user so it's always
# clear where a workspace came from.
SOURCE_PROFILE = "profile"  # ~/.databrickscfg
SOURCE_BUNDLE = "bundle"  # ./databricks.yml (Databricks Asset Bundle)
SOURCE_URL = "url"  # typed in by hand

_SOURCE_LABELS = {
    SOURCE_PROFILE: "~/.databrickscfg",
    SOURCE_BUNDLE: "databricks.yml",
    SOURCE_URL: "manual",
}


@dataclass(frozen=True)
class Workspace:
    """A connection target the login can offer, plus where it came from."""

    profile: str = ""  # ~/.databrickscfg profile name (empty for bundle/url)
    host: str = ""
    source: str = SOURCE_PROFILE
    target: str = ""  # bundle target / display name when there's no profile
    default: bool = False  # pre-select this entry in the picker

    @property
    def host_label(self) -> str:
        return self.host.replace("https://", "").replace("http://", "").rstrip("/")

    @property
    def name(self) -> str:
        return self.profile or self.target or self.host_label or "(workspace)"

    @property
    def source_label(self) -> str:
        base = _SOURCE_LABELS.get(self.source, self.source)
        return f"{base}  ·  default" if self.default else base

    @property
    def label(self) -> str:
        return f"{self.name}  ·  {self.host_label}" if self.host_label else self.name


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
