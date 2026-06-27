"""Domain layer — the model, the rules, and the ports. Pure: no Textual, no SDK,
no asyncio.

Everything here is exercisable in a plain unit test. Infrastructure implements
the ports defined here; the application orchestrates these pieces.
"""

from .errors import AuthError, StoreError
from .host import normalize_host
from .models import (
    CLOUDS,
    AccountWorkspace,
    Acl,
    Cloud,
    Identity,
    Scope,
    Secret,
    Workspace,
    cloud_by_key,
)
from .permissions import AuthSummary, authorization_summary, perm_rank
from .ports import AccountSession, Connected, ProfileStore, WorkspaceConnector
from .secret_store import SecretStore

__all__ = [
    "CLOUDS",
    "AccountSession",
    "AccountWorkspace",
    "Acl",
    "AuthError",
    "AuthSummary",
    "Cloud",
    "Connected",
    "Identity",
    "ProfileStore",
    "Scope",
    "Secret",
    "SecretStore",
    "StoreError",
    "Workspace",
    "WorkspaceConnector",
    "authorization_summary",
    "cloud_by_key",
    "normalize_host",
    "perm_rank",
]
