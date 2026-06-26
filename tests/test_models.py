from __future__ import annotations

import pytest

from keystone.domain import Scope, Secret, Workspace, cloud_by_key, perm_rank
from keystone.domain.models import AccountWorkspace


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


def test_account_workspace_label():
    aw = AccountWorkspace(workspace_id=42, name="analytics", status="RUNNING")
    assert "analytics" in aw.label and "42" in aw.label and "RUNNING" in aw.label


def test_cloud_by_key_hosts():
    assert cloud_by_key("azure").account_host == "https://accounts.azuredatabricks.net"
    assert cloud_by_key("aws").account_host == "https://accounts.cloud.databricks.com"
    assert cloud_by_key("gcp").account_host == "https://accounts.gcp.databricks.com"


def test_cloud_by_key_unknown_raises():
    with pytest.raises(StopIteration):
        cloud_by_key("oracle")
