from __future__ import annotations

import pytest

from isolinear.domain import (
    SOURCE_BUNDLE,
    SOURCE_PROFILE,
    Scope,
    Secret,
    Workspace,
    perm_rank,
)


def test_perm_rank_orders_permissions():
    assert perm_rank("READ") < perm_rank("WRITE") < perm_rank("MANAGE")
    assert perm_rank("nonsense") == 0


@pytest.mark.parametrize(
    ("backend", "is_kv", "icon"),
    [("DATABRICKS", False, "🔒"), ("AZURE_KEYVAULT", True, "☁")],
)
def test_scope_backend_flags(backend, is_kv, icon):
    scope = Scope("s", backend)
    assert scope.is_keyvault is is_kv
    assert scope.icon == icon


def test_secret_last_updated_formats_utc():
    assert Secret("s", "k", None).last_updated == "—"
    # 1_718_000_000_000 ms -> 2024-06-10 (UTC)
    assert Secret("s", "k", 1_718_000_000_000).last_updated.startswith("2024-06-10")


def test_workspace_label_strips_scheme():
    ws = Workspace("prod", "https://x.cloud.databricks.com/")
    assert ws.label == "prod  ·  x.cloud.databricks.com"


def test_profile_workspace_name_and_source():
    ws = Workspace(profile="prod", host="https://prod.cloud.databricks.com")
    assert ws.source == SOURCE_PROFILE
    assert ws.name == "prod"
    assert ws.source_label == "~/.databrickscfg"


def test_bundle_workspace_name_source_and_default_marker():
    ws = Workspace(
        host="https://dab.cloud.databricks.com",
        source=SOURCE_BUNDLE,
        target="acme",
        default=True,
    )
    assert ws.name == "acme"  # no profile -> falls back to the bundle target
    assert ws.host_label == "dab.cloud.databricks.com"
    assert ws.source_label == "databricks.yml  ·  default"
