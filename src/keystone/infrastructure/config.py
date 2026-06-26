"""Location of the Databricks CLI config file."""

from __future__ import annotations

import os
from pathlib import Path


def config_path() -> Path:
    override = os.environ.get("DATABRICKS_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".databrickscfg"
