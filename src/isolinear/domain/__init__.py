"""Domain layer — the model, the rules, and the ports. Pure: no Textual, no SDK,
no asyncio.

Everything here is exercisable in a plain unit test. Infrastructure implements
the ports defined here; the application orchestrates these pieces.
"""

from .errors import AuthError, StoreError
from .host import normalize_host
from .models import (
    SOURCE_BUNDLE,
    SOURCE_PROFILE,
    SOURCE_URL,
    STALE_AFTER_DAYS,
    Acl,
    Identity,
    Scope,
    Secret,
    Workspace,
)
from .permissions import AuthSummary, authorization_summary, perm_rank
from .ports import BundleStore, Connected, ProfileStore, WorkspaceConnector
from .secret_store import SecretStore

__all__ = [
    "SOURCE_BUNDLE",
    "SOURCE_PROFILE",
    "SOURCE_URL",
    "STALE_AFTER_DAYS",
    "Acl",
    "AuthError",
    "AuthSummary",
    "BundleStore",
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
    "normalize_host",
    "perm_rank",
]
