"""MCP Client – connects to any MCP server and runs an interactive
Claude-powered chat loop with the server's tools available.

Usage:
    uv run client.py <path_to_mcp_server_script>

Example:
    uv run client.py server.py
    uv run client.py /path/to/server.js
"""

import asyncio
import os
import sys
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

if not os.environ.get("ANTHROPIC_API_KEY"):
    print(
        "Error: ANTHROPIC_API_KEY is not set.\n"
        "Copy .env.example to .env and add your Anthropic API key.",
        file=sys.stderr,
    )
    sys.exit(1)


async def run(server_script_path: str) -> None:
    """Start the MCP server, connect a client session, then run the chat loop."""

    # Determine the command to launch the server based on file extension.
    if server_script_path.endswith(".py"):
        command = "python"
    elif server_script_path.endswith(".js"):
        command = "node"
    else:
        raise ValueError(
            f"Unsupported server script type: '{server_script_path}'. "
            "Expected a .py or .js file."
        )

    server_params = StdioServerParameters(
        command=command,
        args=[server_script_path],
        env=None,
    )

    anthropic = Anthropic()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Discover tools exposed by the MCP server.
            tools_response = await session.list_tools()
            tools: list[dict[str, Any]] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools_response.tools
            ]

            if tools:
                print("Connected to MCP server.  Available tools:")
                for tool in tools:
                    print(f"  • {tool['name']}: {tool.get('description', '')}")
            else:
                print("Connected to MCP server (no tools exposed).")

            print("\nType your message and press Enter.  Type 'quit' or 'exit' to stop.\n")

            messages: list[dict[str, Any]] = []

            while True:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    break

                if not user_input:
                    continue
                if user_input.lower() in {"quit", "exit"}:
                    print("Goodbye!")
                    break

                messages.append({"role": "user", "content": user_input})

                # Agentic loop: keep calling Claude until no more tool use.
                while True:
                    response = anthropic.messages.create(
                        model="claude-opus-4-5",
                        max_tokens=8192,
                        tools=tools,
                        messages=messages,
                    )

                    # Collect all tool-use blocks in this response.
                    tool_use_blocks = [
                        block
                        for block in response.content
                        if block.type == "tool_use"
                    ]

                    if not tool_use_blocks:
                        # No tool calls – extract and print the final text reply.
                        final_text = " ".join(
                            block.text
                            for block in response.content
                            if hasattr(block, "text")
                        )
                        print(f"\nAssistant: {final_text}\n")
                        messages.append(
                            {"role": "assistant", "content": response.content}
                        )
                        break

                    # There are tool calls: execute each one via the MCP server.
                    messages.append(
                        {"role": "assistant", "content": response.content}
                    )

                    tool_results: list[dict[str, Any]] = []
                    for block in tool_use_blocks:
                        print(f"  [tool call] {block.name}({block.input})")
                        result = await session.call_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result.content,
                            }
                        )

                    messages.append(
                        {"role": "user", "content": tool_results}
                    )
                    # Continue the loop so Claude can process the tool results.


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path_to_mcp_server_script>")
        sys.exit(1)

    asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    main()
