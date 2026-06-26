from __future__ import annotations

from keystone.core import discover_workspaces


def _write_cfg(tmp_path, body: str, monkeypatch):
    cfg = tmp_path / "databrickscfg"
    cfg.write_text(body)
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(cfg))
    return cfg


def test_discover_parses_profiles_including_default(tmp_path, monkeypatch):
    _write_cfg(
        tmp_path,
        """
[DEFAULT]
host = https://default.cloud.databricks.com
token = dapi-x

[staging]
host = https://staging.cloud.databricks.com
auth_type = external-browser
""",
        monkeypatch,
    )
    profiles = {w.profile: w for w in discover_workspaces()}
    assert set(profiles) == {"DEFAULT", "staging"}
    assert profiles["staging"].host == "https://staging.cloud.databricks.com"


def test_discover_skips_sections_without_host(tmp_path, monkeypatch):
    _write_cfg(
        tmp_path,
        """
[has-host]
host = https://a.databricks.com

[no-host]
token = dapi-y
""",
        monkeypatch,
    )
    assert [w.profile for w in discover_workspaces()] == ["has-host"]


def test_env_fallback_when_no_config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(tmp_path / "missing"))
    monkeypatch.setenv("DATABRICKS_HOST", "https://env.databricks.com")
    profiles = discover_workspaces()
    assert len(profiles) == 1
    assert profiles[0].host == "https://env.databricks.com"
