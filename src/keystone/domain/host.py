"""Host — a small domain rule about workspace URLs."""

from __future__ import annotations

from .errors import AuthError


def normalize_host(host: str) -> str:
    """Canonicalize a workspace URL; reject an empty one."""
    host = (host or "").strip()
    if not host:
        raise AuthError("Workspace URL is required.")
    if not host.startswith(("http://", "https://")):
        host = "https://" + host
    return host.rstrip("/")
