import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

CYAN = "\033[36m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
RED = "\033[31m"
WHITE = "\033[97m"
YELLOW = "\033[33m"


def style(prefix: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{prefix}{text}{RESET}"


def print_banner() -> None:
    print()
    print(style(CYAN + BOLD, "  ╭─────────────────────────────────────╮"))
    print(
        style(CYAN + BOLD, "  │")
        + style(WHITE + BOLD, "          MCP Client Console          ")
        + style(CYAN + BOLD, "│")
    )
    print(style(CYAN + BOLD, "  ╰─────────────────────────────────────╯"))


def print_rule(label: str | None = None) -> None:
    width = 37
    if label:
        content = f" {label} ".center(width, "─")
    else:
        content = "─" * width
    print(style(DIM, f"  {content}"))


def print_info(message: str) -> None:
    print(style(DIM, f"  ℹ {message}"))


def print_assistant(message: str) -> None:
    print()
    print_rule("assistant")
    for line in message.splitlines() or [""]:
        print(style(CYAN, f"  {line}"))


def print_tool_call(name: str, arguments: dict[str, Any]) -> None:
    print()
    print(style(YELLOW + BOLD, f"  ⚙ Tool call: {name}"))
    if not arguments:
        print(style(DIM, "    (no arguments)"))
        return
    for key, value in arguments.items():
        rendered = json.dumps(value, indent=2, ensure_ascii=False)
        rendered_lines = rendered.splitlines() or [rendered]
        print(style(DIM, f"    {key}: {rendered_lines[0]}"))
        for line in rendered_lines[1:]:
            print(style(DIM, f"      {line}"))


def print_tool_result(result: str) -> None:
    for line in result.splitlines() or [""]:
        print(style(GREEN, f"  │ {line}"))


def prompt_user() -> str:
    try:
        return input(style(MAGENTA + BOLD, "\n  You ❯ "))
    except (EOFError, KeyboardInterrupt):
        return "/exit"


class MCPClient:
    def __init__(self) -> None:
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.messages: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []

    async def connect_to_server(self, command: str, args: list[str]) -> None:
        server_params = StdioServerParameters(command=command, args=args, env=None)

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self.session.initialize()
        await self.refresh_tools()

    async def refresh_tools(self) -> None:
        if not self.session:
            return

        response = await self.session.list_tools()
        self.tools = [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

        tool_names = ", ".join(style(YELLOW, tool["name"]) for tool in self.tools) or "none"
        print_info(f"Loaded {len(self.tools)} tool(s): {tool_names}")

    async def process_query(self, query: str) -> str:
        if not self.session:
            raise RuntimeError("Client session is not initialized.")

        self.messages.append({"role": "user", "content": query})

        while True:
            response = self.anthropic.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=self.messages,
                tools=self.tools,
            )

            assistant_text: list[str] = []
            tool_uses: list[Any] = []

            for content in response.content:
                if content.type == "text":
                    assistant_text.append(content.text)
                elif content.type == "tool_use":
                    tool_uses.append(content)

            if assistant_text:
                print_assistant("\n".join(assistant_text))

            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return "\n".join(assistant_text)

            tool_results: list[dict[str, Any]] = []
            for tool_use in tool_uses:
                print_tool_call(tool_use.name, tool_use.input)
                result = await self.session.call_tool(tool_use.name, tool_use.input)
                result_text = "\n".join(
                    block.text if hasattr(block, "text") else str(block)
                    for block in result.content
                )
                print_tool_result(result_text)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result_text,
                    }
                )

            self.messages.append({"role": "user", "content": tool_results})

    async def chat_loop(self) -> None:
        print_banner()
        if self.tools:
            print_rule("tools")
            for tool in self.tools:
                description = tool["description"] or "No description provided."
                print(style(YELLOW, f"  • {tool['name']:<20}") + style(DIM, description))
        print_rule()
        print_info("Type /tools to refresh tools, /clear to reset, or /exit to quit.")

        while True:
            query = prompt_user()
            command = query.strip().lower()

            if command in {"exit", "quit", "/exit", "/quit"}:
                print(style(DIM, "\n  Goodbye.\n"))
                break
            if command == "/tools":
                await self.refresh_tools()
                continue
            if command == "/clear":
                self.messages.clear()
                print_info("Conversation history cleared.")
                continue
            if not query.strip():
                continue

            await self.process_query(query)

    async def cleanup(self) -> None:
        await self.exit_stack.aclose()


async def main() -> None:
    if len(sys.argv) < 2:
        print(style(RED, "\nUsage: python client.py <server_command> [server_args...]\n"))
        raise SystemExit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1], sys.argv[2:])
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())