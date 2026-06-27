"""Application layer — use-cases that orchestrate the domain.

Depends only on `domain`; never on infrastructure or the UI. The read model
(`WorkspaceCache`) is pure in-memory app state, so it lives here too.
"""

from .onboarding import Connection, OnboardingService
from .read_model import WorkspaceCache
from .workspace import WorkspaceService

__all__ = [
    "Connection",
    "OnboardingService",
    "WorkspaceCache",
    "WorkspaceService",
]
