"""Ports — the domain's outbound contracts for all I/O.

Infrastructure implements these; the application depends only on them. Together
with `SecretStore` (in secret_store.py) they are every door out of the domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .models import AccountWorkspace, Workspace
from .secret_store import SecretStore


@dataclass
class Connected:
    """The result of establishing a connection: a store plus how to label and
    (optionally) persist it."""

    store: SecretStore
    label: str
    host: str = ""


@runtime_checkable
class AccountSession(Protocol):
    """A live account-discovery session — lists workspaces and connects to one,
    reusing a single authenticated session."""

    @property
    def workspaces(self) -> list[AccountWorkspace]: ...
    def connect(self, ws: AccountWorkspace) -> Connected: ...


@runtime_checkable
class WorkspaceConnector(Protocol):
    """Establishes connections to a secret backend (login / discovery)."""

    def connect_profile(self, profile: str) -> Connected: ...
    def connect_url(self, host: str) -> Connected: ...
    def discover_account(self, cloud_key: str, account_id: str) -> AccountSession: ...


@runtime_checkable
class ProfileStore(Protocol):
    """Reads and writes saved connection profiles."""

    def discover(self) -> list[Workspace]: ...
    def save(self, name: str, host: str, account_id: str | None = None) -> None: ...
