"""Shared fixtures."""

from __future__ import annotations

import pytest

from fakes import FakeGateway, seeded_gateway
from keystone.core import WorkspaceSession


@pytest.fixture
def fake_gateway() -> FakeGateway:
    return seeded_gateway()


@pytest.fixture
def session(fake_gateway: FakeGateway) -> WorkspaceSession:
    """A session whose scopes/secrets/acls are already warmed."""
    s = WorkspaceSession(fake_gateway, "test")
    s.authenticate()
    s.load_scopes()
    for scope in s.scopes:
        s.warm_scope(scope.name)
    return s
