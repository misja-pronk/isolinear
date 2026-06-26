"""Shared fixtures."""

from __future__ import annotations

import pytest

from fakes import FakeSecretStore, seeded_store
from keystone.application import WorkspaceService


@pytest.fixture
def fake_store() -> FakeSecretStore:
    return seeded_store()


@pytest.fixture
def session(fake_store: FakeSecretStore) -> WorkspaceService:
    """A session whose scopes/secrets/acls are already warmed."""
    s = WorkspaceService(fake_store, "test")
    s.authenticate()
    s.load_scopes()
    for scope in s.scopes:
        s.warm_scope(scope.name)
    return s
