"""
MCP Client — connects to an MCP server and chats with Claude.

Usage:
    python client.py <path/to/mcp_server.py>        # stdio server
    python client.py <command> [args...]             # any stdio server
"""

import asyncio
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

# ── terminal colours ──────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
MAGENTA = "\033[35m"
RED    = "\033[31m"
WHITE  = "\033[97m"

def _c(color: str, text: str) -> str:
    """Wrap text in a colour + reset."""
    return f"{color}{text}{RESET}"


def _banner() -> None:
    lines = [
        "",
        _c(CYAN + BOLD, "  ╔══════════════════════════════════════╗"),
        _c(CYAN + BOLD, "  ║") + _c(WHITE + BOLD, "          MCP Client  🤖            ") + _c(CYAN + BOLD, "║"),
        _c(CYAN + BOLD, "  ╚══════════════════════════════════════╝"),
        "",
    ]
    print("\n".join(lines))


def _rule(label: str = "") -> None:
    width = 44
    if label:
        pad   = (width - len(label) - 2) // 2
        line  = "─" * pad + f" {label} " + "─" * pad
    else:
        line = "─" * width
    print(_c(DIM, f"  {line}"))


def _info(msg: str) -> None:
    print(_c(DIM, f"  ℹ  {msg}"))


def _tool_call(name: str, args: dict[str, Any]) -> None:
    print(_c(YELLOW, f"\n  ⚙  Tool call → ") + _c(BOLD + YELLOW, name))
    for k, v in args.items():
        print(_c(DIM, f"      {k}: ") + str(v))


def _tool_result(content: str) -> None:
    for line in content.splitlines():
        print(_c(GREEN, "  │ ") + _c(DIM, line))


def _assistant(text: str) -> None:
    print()
    _rule("assistant")
    for line in text.splitlines():
        print(_c(CYAN, "  ") + line)
    print()


def _prompt() -> str:
    try:
        return input(_c(MAGENTA + BOLD, "\n  You ❯ "))
    except (EOFError, KeyboardInterrupt):
        return "/exit"


# ── MCP client ────────────────────────────────────────────────────────────────

class MCPClient:
    MODEL = "claude-opus-4-5"

    def __init__(self) -> None:
        self._stack    = AsyncExitStack()
        self._session: ClientSession | None = None
        self._anthropic = Anthropic()
        self._history: list[dict] = []
        self._tools:   list[dict] = []

    # ── lifecycle ──────────────────────────────────────────────────────────

    async def connect(self, *server_argv: str) -> None:
        """Spawn an MCP server over stdio and initialise the session."""
        params = StdioServerParameters(
            command=server_argv[0],
            args=list(server_argv[1:]),
            env=None,
        )
        transport = await self._stack.enter_async_context(stdio_client(params))
        read, write = transport
        self._session = await self._stack.enter_async_context(
            ClientSession(read, write)
        )
        await self._session.initialize()
        await self._refresh_tools()

    async def _refresh_tools(self) -> None:
        assert self._session
        resp = await self._session.list_tools()
        self._tools = [
            {
                "name":        t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema,
            }
            for t in resp.tools
        ]
        _info(f"Loaded {len(self._tools)} tool(s): " +
              ", ".join(_c(YELLOW, t["name"]) for t in self._tools))

    async def close(self) -> None:
        await self._stack.aclose()

    # ── chat ───────────────────────────────────────────────────────────────

    async def chat(self, user_text: str) -> str:
        self._history.append({"role": "user", "content": user_text})

        while True:
            response = self._anthropic.messages.create(
                model=self.MODEL,
                max_tokens=4096,
                tools=self._tools,
                messages=self._history,
            )

            # collect text blocks
            text_parts: list[str] = []
            tool_uses: list[Any]  = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            # stream text to the user
            if text_parts:
                _assistant("\n".join(text_parts))

            # if no tool calls we're done
            if response.stop_reason != "tool_use":
                final = "\n".join(text_parts)
                self._history.append({"role": "assistant", "content": response.content})
                return final

            # execute every tool the model requested
            self._history.append({"role": "assistant", "content": response.content})
            tool_results: list[dict] = []

            for tu in tool_uses:
                _tool_call(tu.name, tu.input)
                assert self._session
                result = await self._session.call_tool(tu.name, tu.input)
                raw = "\n".join(
                    (c.text if hasattr(c, "text") else str(c))
                    for c in result.content
                )
                _tool_result(raw)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tu.id,
                    "content":     raw,
                })

            self._history.append({"role": "user", "content": tool_results})
            # loop → model sees results and continues

    # ── REPL ──────────────────────────────────────────────────────────────

    async def repl(self) -> None:
        _banner()
        if self._tools:
            _rule("tools available")
            for t in self._tools:
                print(
                    _c(YELLOW, f"  • {t['name']:<20}")
                    + _c(DIM, t["description"][:60])
                )
        _rule()
        _info("Type " + _c(BOLD, "/exit") + " or press Ctrl-C to quit.")

        while True:
            user_input = _prompt()
            cmd = user_input.strip().lower()

            if cmd in ("/exit", "/quit", "exit", "quit"):
                print(_c(DIM, "\n  Goodbye.\n"))
                break
            if cmd == "/tools":
                await self._refresh_tools()
                continue
            if cmd == "/clear":
                self._history.clear()
                _info("Conversation history cleared.")
                continue
            if not user_input.strip():
                continue

            await self.chat(user_input)


# ── entry-point ───────────────────────────────────────────────────────────────

async def main() -> None:
    if len(sys.argv) < 2:
        print(
            _c(RED, "\nUsage: ")
            + "python client.py <server_command> [args...]\n"
        )
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect(*sys.argv[1:])
        await client.repl()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
