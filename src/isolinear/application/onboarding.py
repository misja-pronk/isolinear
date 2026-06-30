"""OnboardingService — connection/login use-cases.

Depends only on domain ports (`WorkspaceConnector`, `ProfileStore`, `BundleStore`);
the composition root injects concrete infrastructure adapters. Produces
ready-to-use `WorkspaceService` instances so the UI never touches the store or
the SDK.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain import (
    SOURCE_PROFILE,
    BundleStore,
    ProfileStore,
    Workspace,
    WorkspaceConnector,
)
from .workspace import WorkspaceService


@dataclass
class Connection:
    """A live workspace session plus the host needed to persist it as a profile."""

    service: WorkspaceService
    host: str = ""


class OnboardingService:
    def __init__(
        self,
        connector: WorkspaceConnector,
        profiles: ProfileStore,
        bundle: BundleStore | None = None,
    ) -> None:
        self._connector = connector
        self._profiles = profiles
        self._bundle = bundle

    # -- discovery ------------------------------------------------------
    def available_workspaces(self) -> list[Workspace]:
        """Every workspace we can offer, each tagged with where it came from: the
        bundle target (default) first, then the ~/.databrickscfg profiles."""
        workspaces: list[Workspace] = []
        seen: set[str] = set()
        bundle = self._bundle.discover() if self._bundle else None
        if bundle:
            workspaces.append(bundle)
            seen.add(bundle.host_label)
        for ws in self._profiles.discover():
            if ws.host_label and ws.host_label in seen:
                continue  # already offered by the bundle
            seen.add(ws.host_label)
            workspaces.append(ws)
        return workspaces

    def save_profile(self, name: str, host: str) -> None:
        self._profiles.save(name, host)

    # -- connection use-cases -------------------------------------------
    def connect(self, workspace: Workspace) -> Connection:
        """Connect to a chosen workspace. A saved profile uses its stored auth; a
        bundle target or manual URL signs in through the browser (OAuth)."""
        if workspace.source == SOURCE_PROFILE and workspace.profile:
            return self.connect_profile(workspace.profile)
        return self.connect_url(workspace.host)

    def connect_profile(self, profile: str) -> Connection:
        c = self._connector.connect_profile(profile)
        return Connection(WorkspaceService(c.store, c.label))

    def connect_url(self, host: str) -> Connection:
        c = self._connector.connect_url(host)
        return Connection(WorkspaceService(c.store, c.label), host=c.host)
