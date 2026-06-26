from __future__ import annotations

import pytest

from keystone.domain import AuthError, normalize_host


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("x.cloud.databricks.com", "https://x.cloud.databricks.com"),
        ("https://x.databricks.com/", "https://x.databricks.com"),
        ("  http://h/  ", "http://h"),
    ],
)
def test_normalize_host(raw, expected):
    assert normalize_host(raw) == expected


def test_normalize_host_empty_raises():
    with pytest.raises(AuthError):
        normalize_host("   ")
