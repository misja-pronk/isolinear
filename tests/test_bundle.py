from __future__ import annotations

import textwrap

from isolinear.domain import SOURCE_BUNDLE
from isolinear.infrastructure.bundle import DatabricksBundleStore


def _write(tmp_path, body: str) -> DatabricksBundleStore:
    (tmp_path / "databricks.yml").write_text(textwrap.dedent(body))
    return DatabricksBundleStore(root=tmp_path)


def test_no_file_returns_none(tmp_path):
    assert DatabricksBundleStore(root=tmp_path).discover() is None


def test_picks_the_default_target(tmp_path):
    store = _write(
        tmp_path,
        """
        bundle:
          name: acme
        targets:
          dev:
            workspace:
              host: https://dev.cloud.databricks.com
          prod:
            default: true
            workspace:
              host: https://prod.cloud.databricks.com
        """,
    )
    ws = store.discover()
    assert ws is not None
    assert ws.source == SOURCE_BUNDLE and ws.default is True
    assert ws.host == "https://prod.cloud.databricks.com"
    assert ws.target == "prod"


def test_single_target_is_used(tmp_path):
    store = _write(
        tmp_path,
        """
        bundle:
          name: solo
        targets:
          only:
            workspace:
              host: https://only.cloud.databricks.com
        """,
    )
    ws = store.discover()
    assert ws is not None and ws.target == "only"
    assert ws.host == "https://only.cloud.databricks.com"


def test_top_level_host_fallback_uses_bundle_name(tmp_path):
    store = _write(
        tmp_path,
        """
        bundle:
          name: toplevel
        workspace:
          host: https://top.cloud.databricks.com
        """,
    )
    ws = store.discover()
    assert ws is not None
    assert ws.host == "https://top.cloud.databricks.com"
    assert ws.target == "toplevel"


def test_unresolved_variable_is_skipped(tmp_path):
    store = _write(
        tmp_path,
        """
        workspace:
          host: ${var.host}
        """,
    )
    assert store.discover() is None


def test_no_host_returns_none(tmp_path):
    assert _write(tmp_path, "bundle:\n  name: empty\n").discover() is None


def test_bare_host_is_normalized(tmp_path):
    store = _write(
        tmp_path,
        """
        workspace:
          host: bare.cloud.databricks.com
        """,
    )
    ws = store.discover()
    assert ws is not None and ws.host == "https://bare.cloud.databricks.com"
