"""
Claude MCP Connector client.

Calls the Claude Messages API with a remote MCP server attached via the
MCP connector (beta).  Anthropic makes the MCP connection server-side, so
there is nothing extra to run locally.

Two request pieces are required and must share the same server name:
  * mcp_servers  — connection descriptor {type, url, name, [authorization_token]}
  * tools        — an mcp_toolset entry that references the server by name

Configuration (via environment variables or a .env file):
  ANTHROPIC_API_KEY  — required; your Anthropic API key
  MCP_SERVER_URL     — remote MCP server endpoint (Streamable HTTP / SSE)
  MCP_SERVER_TOKEN   — optional bearer token forwarded to the MCP server

Basic usage:
  from client import ClaudeMcpService
  result = ClaudeMcpService().call("What tools can you use?")
  print(result.text)

CLI usage:
  python client.py "What tools can you use?"
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "claude-opus-4-5-20251101"
MCP_BETA = "mcp-client-2025-11-20"
SERVER_NAME = "example-mcp"


@dataclass
class Result:
    text: str
    stop_reason: str
    message: Any = field(repr=False)


class ClaudeMcpService:
    """Wraps the Claude beta Messages API with a remote MCP server attached."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        server_url: str | None = None,
        server_token: str | None = None,
        allowed_tools: list[str] | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self._server_url = (
            server_url if server_url is not None else os.environ.get("MCP_SERVER_URL", "")
        )
        self._server_token = (
            server_token if server_token is not None else os.environ.get("MCP_SERVER_TOKEN", "")
        )
        self._allowed_tools = allowed_tools
        self._model = model

    def call(self, prompt: str, *, max_tokens: int = 16_000) -> Result:
        """Send a single user message and return the assistant's response."""
        if not self._server_url:
            raise ValueError("MCP_SERVER_URL is not configured")

        message = self._client.beta.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            betas=[MCP_BETA],
            mcp_servers=[self._mcp_server()],
            tools=[self._mcp_toolset()],
            messages=[{"role": "user", "content": prompt}],
        )

        return Result(
            text=self._extract_text(message),
            stop_reason=message.stop_reason,
            message=message,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _mcp_server(self) -> dict:
        server: dict = {"type": "url", "url": self._server_url, "name": SERVER_NAME}
        if self._server_token:
            server["authorization_token"] = self._server_token
        return server

    def _mcp_toolset(self) -> dict:
        toolset: dict = {"type": "mcp_toolset", "mcp_server_name": SERVER_NAME}
        if self._allowed_tools is not None:
            toolset["default_config"] = {"enabled": False}
            toolset["configs"] = [
                {"name": name, "enabled": True} for name in self._allowed_tools
            ]
        return toolset

    @staticmethod
    def _extract_text(message: Any) -> str:
        return "\n".join(
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        )


def main() -> None:
    prompt = (
        " ".join(sys.argv[1:])
        or "List the tools you have access to and what each one does."
    )
    result = ClaudeMcpService().call(prompt)
    print(f"stop_reason: {result.stop_reason}")
    print("---")
    print(result.text)


if __name__ == "__main__":
    main()
