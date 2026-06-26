"""OnboardingService — connection/login use-cases.

Depends only on domain ports (`WorkspaceConnector`, `ProfileStore`); the
composition root injects concrete infrastructure adapters. Produces ready-to-use
`WorkspaceService` instances so the UI never touches the store or the SDK.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import (
    AccountSession,
    AccountWorkspace,
    ProfileStore,
    Workspace,
    WorkspaceConnector,
)
from .workspace import WorkspaceService


@dataclass
class Connection:
    """A live workspace session plus what's needed to persist it as a profile."""

    service: WorkspaceService
    host: str = ""
    account_id: str | None = None


class OnboardingService:
    def __init__(self, connector: WorkspaceConnector, profiles: ProfileStore) -> None:
        self._connector = connector
        self._profiles = profiles

    # -- saved profiles -------------------------------------------------
    def saved_workspaces(self) -> list[Workspace]:
        return self._profiles.discover()

    def save_profile(self, name: str, host: str, account_id: str | None = None) -> None:
        self._profiles.save(name, host, account_id)

    # -- connection use-cases -------------------------------------------
    def connect_profile(self, profile: str) -> Connection:
        c = self._connector.connect_profile(profile)
        return Connection(WorkspaceService(c.store, c.label))

    def connect_url(self, host: str) -> Connection:
        c = self._connector.connect_url(host)
        return Connection(WorkspaceService(c.store, c.label), host=c.host)

    def discover_account(self, cloud_key: str, account_id: str) -> AccountSession:
        return self._connector.discover_account(cloud_key, account_id)

    def connect_account_workspace(
        self,
        session: AccountSession,
        ws: AccountWorkspace,
        account_id: str | None = None,
    ) -> Connection:
        c = session.connect(ws)
        return Connection(
            WorkspaceService(c.store, c.label), host=c.host, account_id=account_id
        )
