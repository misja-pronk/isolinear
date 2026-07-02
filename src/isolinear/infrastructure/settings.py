"""JSON-file settings adapter — persisted UI preferences, never secrets.

Lives at `$XDG_CONFIG_HOME/isolinear/settings.json` (default
`~/.config/isolinear/settings.json`). Deliberately forgiving: a missing,
corrupt, or partial file yields defaults instead of an error, so a bad write
can never keep the app from starting.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, fields
from pathlib import Path

from ..domain import Settings


def settings_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base).expanduser() / "isolinear" / "settings.json"


class JsonSettingsStore:
    """`SettingsStore` backed by a small JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or settings_path()

    def load(self) -> Settings:
        try:
            raw = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return Settings()
        if not isinstance(raw, dict):
            return Settings()
        defaults = Settings()
        kwargs = {
            f.name: raw[f.name]
            for f in fields(Settings)
            if isinstance(raw.get(f.name), type(getattr(defaults, f.name)))
        }
        return Settings(**kwargs)

    def save(self, settings: Settings) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(asdict(settings), indent=2) + "\n")
        except OSError:
            pass  # preferences are best-effort; never crash the app over them
