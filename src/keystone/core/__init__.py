"""Pure domain + service layer. No Textual imports live below this package.

Anything in `core` can be exercised in a plain unit test without an event loop
or a live Databricks connection (substitute a fake `Gateway`).
"""

from .cache import WorkspaceCache
from .config import config_path, discover_workspaces
from .gateway import DatabricksGateway, Gateway, GatewayError
from .models import (
    CLOUDS,
    AccountWorkspace,
    Acl,
    AuthSummary,
    Cloud,
    Identity,
    Scope,
    Secret,
    Workspace,
    cloud_by_key,
    perm_rank,
)
from .session import WorkspaceSession

__all__ = [
    "CLOUDS",
    "Acl",
    "AccountWorkspace",
    "AuthSummary",
    "Cloud",
    "DatabricksGateway",
    "Gateway",
    "GatewayError",
    "Identity",
    "Scope",
    "Secret",
    "Workspace",
    "WorkspaceCache",
    "WorkspaceSession",
    "cloud_by_key",
    "config_path",
    "discover_workspaces",
    "perm_rank",
]
