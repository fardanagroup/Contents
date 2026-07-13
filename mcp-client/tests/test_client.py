"""Tests for ClaudeMcpService — mirrors the Ruby minitest suite from the
referenced codespaces-rails commit."""

from __future__ import annotations

import pytest

from client import SERVER_NAME, ClaudeMcpService


def build(**kwargs) -> ClaudeMcpService:
    return ClaudeMcpService(
        api_key="test-key",
        server_url="https://mcp.example/sse",
        **kwargs,
    )


# ------------------------------------------------------------------
# _mcp_server
# ------------------------------------------------------------------


def test_mcp_server_carries_type_url_and_server_name():
    server = build()._mcp_server()
    assert server["type"] == "url"
    assert server["url"] == "https://mcp.example/sse"
    assert server["name"] == SERVER_NAME


def test_mcp_server_omits_authorization_token_when_no_token():
    server = build(server_token=None)._mcp_server()
    assert "authorization_token" not in server


def test_mcp_server_includes_authorization_token_when_token_set():
    server = build(server_token="secret")._mcp_server()
    assert server["authorization_token"] == "secret"


# ------------------------------------------------------------------
# _mcp_toolset
# ------------------------------------------------------------------


def test_mcp_toolset_references_server_name_and_exposes_all_tools_by_default():
    toolset = build()._mcp_toolset()
    assert toolset["type"] == "mcp_toolset"
    assert toolset["mcp_server_name"] == SERVER_NAME
    # No allowlist → no default_config/configs keys
    assert "default_config" not in toolset
    assert "configs" not in toolset


def test_allowed_tools_switches_toolset_to_allowlist_mode():
    toolset = build(allowed_tools=["example_tool_1", "example_tool_2"])._mcp_toolset()
    assert toolset["default_config"] == {"enabled": False}
    assert toolset["configs"] == [
        {"name": "example_tool_1", "enabled": True},
        {"name": "example_tool_2", "enabled": True},
    ]


# ------------------------------------------------------------------
# call
# ------------------------------------------------------------------


def test_call_raises_when_server_url_is_missing():
    service = ClaudeMcpService(api_key="test-key", server_url=None)
    with pytest.raises(ValueError, match="MCP_SERVER_URL"):
        service.call("hi")
