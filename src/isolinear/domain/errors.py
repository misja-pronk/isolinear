"""Domain-level error types — abstractions the application catches without
knowing (or caring) that the backend is Databricks."""

from __future__ import annotations


class StoreError(Exception):
    """A secret-store operation failed; carries a UI-friendly message."""


class AuthError(Exception):
    """Login / workspace-discovery failure; carries a UI-friendly message."""
