from __future__ import annotations

import configparser

import pytest

from dbxvault.core import auth


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("x.cloud.databricks.com", "https://x.cloud.databricks.com"),
        ("https://x.databricks.com/", "https://x.databricks.com"),
        ("  http://h/  ", "http://h"),
    ],
)
def test_normalize_host(raw, expected):
    assert auth.normalize_host(raw) == expected


def test_normalize_host_empty_raises():
    with pytest.raises(auth.AuthError):
        auth.normalize_host("   ")


def test_save_profile_roundtrip(tmp_path, monkeypatch):
    cfg = tmp_path / "databrickscfg"
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(cfg))

    auth.save_profile("prod", "prod.cloud.databricks.com")
    auth.save_profile("acct", "https://accounts.azuredatabricks.net", account_id="abc-1")

    parser = configparser.ConfigParser()
    parser.read(cfg)
    assert parser["prod"]["host"] == "https://prod.cloud.databricks.com"
    assert parser["prod"]["auth_type"] == "external-browser"
    assert parser["acct"]["account_id"] == "abc-1"


def test_save_profile_updates_existing(tmp_path, monkeypatch):
    cfg = tmp_path / "databrickscfg"
    monkeypatch.setenv("DATABRICKS_CONFIG_FILE", str(cfg))
    auth.save_profile("prod", "https://old.databricks.com")
    auth.save_profile("prod", "https://new.databricks.com")
    parser = configparser.ConfigParser()
    parser.read(cfg)
    assert parser["prod"]["host"] == "https://new.databricks.com"
