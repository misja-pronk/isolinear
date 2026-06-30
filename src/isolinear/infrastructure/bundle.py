"""DatabricksBundleStore — the `BundleStore` port over a Databricks Asset Bundle.

If a `databricks.yml` sits in the working directory, its target workspace becomes
the *default* connection Isolinear offers — so running `isolinear` inside a bundle
project just works. We pick the target flagged `default: true` (or the only one),
fall back to the top-level `workspace.host`, and skip anything still templated
with `${...}` variables we can't resolve.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..domain import SOURCE_BUNDLE, Workspace, normalize_host

# Filenames the Databricks CLI accepts for a bundle, in priority order.
_BUNDLE_FILES = ("databricks.yml", "databricks.yaml", "bundle.yml", "bundle.yaml")


class DatabricksBundleStore:
    """Reads the bundle config in `root` (defaults to the current directory)."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path.cwd()

    def _config_file(self) -> Path | None:
        return next((p for n in _BUNDLE_FILES if (p := self._root / n).is_file()), None)

    def discover(self) -> Workspace | None:
        path = self._config_file()
        if path is None:
            return None
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except (OSError, yaml.YAMLError):
            return None
        if not isinstance(data, dict):
            return None

        bundle_name = _dig(data, "bundle", "name") or ""
        target_name, host = _pick_target(data)
        if not host or "${" in host:  # target host missing/unresolved — try top-level
            host = _dig(data, "workspace", "host") or ""
        if not host or "${" in host:  # still missing or an unresolved variable
            return None
        try:
            host = normalize_host(host)
        except Exception:  # noqa: BLE001
            return None
        return Workspace(
            host=host,
            source=SOURCE_BUNDLE,
            target=target_name or bundle_name or "bundle",
            default=True,
        )


def _pick_target(data: dict) -> tuple[str, str]:
    """Return (target_name, host) for the bundle's chosen target — the one flagged
    `default: true`, or the sole target if there's exactly one."""
    targets = data.get("targets")
    if not isinstance(targets, dict) or not targets:
        return "", ""
    chosen = next(
        (n for n, t in targets.items() if isinstance(t, dict) and t.get("default")),
        None,
    )
    if chosen is None and len(targets) == 1:
        chosen = next(iter(targets))
    if chosen is None:
        return "", ""
    return str(chosen), _dig(targets.get(chosen), "workspace", "host") or ""


def _dig(data: object, *keys: str) -> str | None:
    """Safely walk nested mappings; return the leaf only if it's a string."""
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur if isinstance(cur, str) else None
