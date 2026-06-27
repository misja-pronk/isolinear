"""DatabricksCfgProfileStore — the `ProfileStore` port over ~/.databrickscfg."""

from __future__ import annotations

import configparser
import os

from ..domain import Workspace, normalize_host
from .config import config_path


class DatabricksCfgProfileStore:
    def discover(self) -> list[Workspace]:
        """Parse ~/.databrickscfg into a list of Workspace profiles.

        Falls back to an env-var 'DEFAULT' workspace if DATABRICKS_HOST is set
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

    def save(
        self,
        name: str,
        host: str,
        account_id: str | None = None,
        auth_type: str = "external-browser",
    ) -> None:
        """Write a reusable profile into ~/.databrickscfg (mirrors
        `databricks auth login`): host + auth_type, no secret stored."""
        path = config_path()
        parser = configparser.ConfigParser()
        if path.exists():
            parser.read(path)
        name = name.strip() or "isolinear"
        if name != parser.default_section and not parser.has_section(name):
            parser.add_section(name)
        parser.set(name, "host", normalize_host(host))
        parser.set(name, "auth_type", auth_type)
        if account_id:
            parser.set(name, "account_id", account_id.strip())
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as fh:
            parser.write(fh)
