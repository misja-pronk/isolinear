from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from keystone.core import Gateway
from keystone.core.gateway import DatabricksGateway, GatewayError


def _client() -> MagicMock:
    client = MagicMock()
    client.current_user.me.return_value = SimpleNamespace(
        user_name="me@corp.com", display_name="Me"
    )
    client.secrets.list_scopes.return_value = [
        SimpleNamespace(name="prod", backend_type=SimpleNamespace(value="DATABRICKS")),
        SimpleNamespace(name="kv", backend_type=SimpleNamespace(value="AZURE_KEYVAULT")),
    ]
    client.secrets.list_secrets.return_value = [
        SimpleNamespace(key="b", last_updated_timestamp=2),
        SimpleNamespace(key="a", last_updated_timestamp=1),
    ]
    client.secrets.list_acls.return_value = [
        SimpleNamespace(
            principal="me@corp.com", permission=SimpleNamespace(value="MANAGE")
        ),
    ]
    client.secrets.get_secret.return_value = SimpleNamespace(
        value=base64.b64encode(b"hunter2").decode()
    )
    return client


def test_databricks_gateway_satisfies_protocol():
    assert isinstance(DatabricksGateway.from_profile("x"), Gateway)


def test_whoami_success():
    gw = DatabricksGateway.from_client(_client())
    identity = gw.whoami()
    assert identity.authenticated and identity.user_name == "me@corp.com"


def test_whoami_failure_is_captured_not_raised():
    client = MagicMock()
    client.current_user.me.side_effect = RuntimeError("401 Unauthorized\nmore")
    identity = DatabricksGateway.from_client(client).whoami()
    assert not identity.authenticated
    assert identity.error == "401 Unauthorized"  # condensed to first line


def test_list_scopes_maps_and_sorts():
    scopes = DatabricksGateway.from_client(_client()).list_scopes()
    assert [s.name for s in scopes] == ["kv", "prod"]
    assert scopes[0].backend_type == "AZURE_KEYVAULT"


def test_list_secrets_sorted_by_key():
    secrets = DatabricksGateway.from_client(_client()).list_secrets("prod")
    assert [s.key for s in secrets] == ["a", "b"]


def test_get_secret_value_base64_decoded():
    gw = DatabricksGateway.from_client(_client())
    assert gw.get_secret_value("p", "k") == "hunter2"


def test_errors_are_wrapped_in_gateway_error():
    client = MagicMock()
    client.secrets.list_scopes.side_effect = RuntimeError("nope")
    with pytest.raises(GatewayError):
        DatabricksGateway.from_client(client).list_scopes()


def test_mutations_call_sdk():
    client = _client()
    gw = DatabricksGateway.from_client(client)
    gw.put_secret("s", "k", "v")
    gw.delete_secret("s", "k")
    gw.create_scope("new")
    gw.delete_scope("new")
    client.secrets.put_secret.assert_called_once_with(
        scope="s", key="k", string_value="v"
    )
    client.secrets.delete_secret.assert_called_once_with(scope="s", key="k")
    client.secrets.create_scope.assert_called_once_with(scope="new")
    client.secrets.delete_scope.assert_called_once_with(scope="new")


def test_put_acl_maps_permission_to_enum():
    from databricks.sdk.service.workspace import AclPermission

    client = _client()
    DatabricksGateway.from_client(client).put_acl("s", "me@corp.com", "MANAGE")
    client.secrets.put_acl.assert_called_once_with(
        scope="s", principal="me@corp.com", permission=AclPermission.MANAGE
    )


def test_delete_acl_calls_sdk():
    client = _client()
    DatabricksGateway.from_client(client).delete_acl("s", "me@corp.com")
    client.secrets.delete_acl.assert_called_once_with(scope="s", principal="me@corp.com")
