"""Discover Databricks connection profiles (treated as 'workspaces')."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from .models import Workspace


def config_path() -> Path:
    """Location of the Databricks CLI config file."""
    override = os.environ.get("DATABRICKS_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".databrickscfg"


def discover_workspaces() -> list[Workspace]:
    """Parse ~/.databrickscfg into a list of Workspace profiles.

    Falls back to an env-var based 'DEFAULT' workspace if DATABRICKS_HOST is set
    but no config file exists.
    """
    path = config_path()
    workspaces: list[Workspace] = []

    if path.exists():
        parser = configparser.ConfigParser()
        # Databricks uses 'DEFAULT' as a real profile, not just the ini default.
        parser.read(path)
        seen: set[str] = set()
        for name in [parser.default_section, *parser.sections()]:
            if name in seen:
                continue
            seen.add(name)
            if not parser.has_section(name) and name != parser.default_section:
                continue
            host = parser.get(name, "host", fallback="").strip()
            if host:
                workspaces.append(Workspace(profile=name, host=host))

    if not workspaces:
        env_host = os.environ.get("DATABRICKS_HOST", "").strip()
        if env_host:
            workspaces.append(Workspace(profile="DEFAULT", host=env_host))

    return workspaces
