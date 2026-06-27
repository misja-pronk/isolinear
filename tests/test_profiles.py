from __future__ import annotations

import configparser

from isolinear.infrastructure import DatabricksCfgProfileStore


def _store(tmp_path, monkeypatch, body: str = ""):
    cfg = tmp_path / "databrickscfg"
    if body:
        cfg.write_text(body)
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(cfg))
    return DatabricksCfgProfileStore(), cfg


def test_discover_parses_profiles_including_default(tmp_path, monkeypatch):
    store, _ = _store(
        tmp_path,
        monkeypatch,
        """
[DEFAULT]
host = https://default.cloud.databricks.com
token = dapi-x

[staging]
host = https://staging.cloud.databricks.com
auth_type = external-browser
""",
    )
    profiles = {w.profile: w for w in store.discover()}
    assert set(profiles) == {"DEFAULT", "staging"}
    assert profiles["staging"].host == "https://staging.cloud.databricks.com"


def test_discover_skips_sections_without_host(tmp_path, monkeypatch):
    store, _ = _store(
        tmp_path,
        monkeypatch,
        """
[has-host]
host = https://a.databricks.com

[no-host]
token = dapi-y
""",
    )
    assert [w.profile for w in store.discover()] == ["has-host"]


def test_discover_env_fallback_when_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(tmp_path / "missing"))
    monkeypatch.setenv("DATABRICKS_HOST", "https://env.databricks.com")
    profiles = DatabricksCfgProfileStore().discover()
    assert len(profiles) == 1
    assert profiles[0].host == "https://env.databricks.com"


def test_save_roundtrip(tmp_path, monkeypatch):
    store, cfg = _store(tmp_path, monkeypatch)
    store.save("prod", "prod.cloud.databricks.com")
    store.save("acct", "https://accounts.azuredatabricks.net", account_id="abc-1")

    parser = configparser.ConfigParser()
    parser.read(cfg)
    assert parser["prod"]["host"] == "https://prod.cloud.databricks.com"
    assert parser["prod"]["auth_type"] == "external-browser"
    assert parser["acct"]["account_id"] == "abc-1"


def test_save_updates_existing(tmp_path, monkeypatch):
    store, cfg = _store(tmp_path, monkeypatch)
    store.save("prod", "https://old.databricks.com")
    store.save("prod", "https://new.databricks.com")
    parser = configparser.ConfigParser()
    parser.read(cfg)
    assert parser["prod"]["host"] == "https://new.databricks.com"
