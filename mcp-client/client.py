"""An interactive MCP client backed by Claude.

Connects to a single MCP server over stdio, exposes that server's tools to
Claude, and runs a chat loop where Claude can call the tools to answer your
questions.

Usage:
    uv run client.py <path/to/server.py>
    uv run client.py <command> [args...]

Examples:
    uv run client.py ../weather/server.py
    uv run client.py npx -y @modelcontextprotocol/server-filesystem /tmp
"""

import asyncio
import os
import shutil
import sys
from contextlib import AsyncExitStack

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1000"))


class MCPClient:
    """Bridges a stdio MCP server and the Anthropic Messages API."""

    def __init__(self) -> None:
        self.session: ClientSession | None = None
        self._stack = AsyncExitStack()
        self.anthropic = Anthropic()

    async def connect(self, command: str, args: list[str]) -> None:
        """Launch the server process and start an MCP session with it."""
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None,
        )

        stdio, write = await self._stack.enter_async_context(
            stdio_client(server_params)
        )
        self.session = await self._stack.enter_async_context(
            ClientSession(stdio, write)
        )
        await self.session.initialize()

        response = await self.session.list_tools()
        tool_names = ", ".join(tool.name for tool in response.tools) or "(none)"
        print(f"Connected. Available tools: {tool_names}")

    async def _available_tools(self) -> list[dict]:
        """Describe the server's tools in the shape the Anthropic API expects."""
        assert self.session is not None
        response = await self.session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

    @staticmethod
    def _tool_result_text(result: types.CallToolResult) -> str:
        """Flatten an MCP tool result into text for Claude."""
        parts: list[str] = []
        for block in result.content:
            if isinstance(block, types.TextContent):
                parts.append(block.text)
            else:
                parts.append(f"[{block.type} content]")
        return "\n".join(parts)

    async def process_query(self, query: str) -> str:
        """Run one query through Claude, executing any tool calls it requests."""
        assert self.session is not None
        tools = await self._available_tools()
        messages: list[dict] = [{"role": "user", "content": query}]
        output: list[str] = []

        while True:
            response = self.anthropic.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=messages,
                tools=tools,
            )

            assistant_content = []
            tool_uses = []
            for block in response.content:
                assistant_content.append(block)
                if block.type == "text":
                    output.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            messages.append({"role": "assistant", "content": assistant_content})

            if not tool_uses:
                break

            tool_results = []
            for tool_use in tool_uses:
                output.append(f"[calling tool {tool_use.name} with {tool_use.input}]")
                result = await self.session.call_tool(tool_use.name, tool_use.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": self._tool_result_text(result),
                        "is_error": bool(result.isError),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        return "\n".join(output)

    async def chat_loop(self) -> None:
        """Read queries from stdin until the user quits."""
        print("MCP client ready. Type your queries, or 'quit' to exit.")
        while True:
            try:
                query = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if query.lower() in {"quit", "exit"}:
                break
            if not query:
                continue
            try:
                print("\n" + await self.process_query(query))
            except Exception as exc:  # noqa: BLE001 - surface any error to the user
                print(f"\nError: {exc}")

    async def aclose(self) -> None:
        await self._stack.aclose()


async def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY is not set (put it in a .env file).")
        sys.exit(1)

    # First arg is the server: either a script path or an executable command.
    command, *args = sys.argv[1:]
    if command.endswith(".py"):
        args = [command, *args]
        command = sys.executable
    elif shutil.which(command) is None:
        print(f"Error: cannot find command '{command}' on PATH.")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect(command, args)
        await client.chat_loop()
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
