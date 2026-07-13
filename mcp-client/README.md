# MCP Client

A terminal MCP client powered by **Claude** with colour-coded, easy-to-read output.

## Features

- Connects to any MCP server over stdio
- Agentic loop — Claude autonomously calls tools until it has a complete answer
- Coloured terminal output: user prompts, assistant replies, tool calls, and tool results each have a distinct style
- Built-in REPL commands: `/tools`, `/clear`, `/exit`
- Conversation history preserved across turns within a session

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) **or** pip
- An `ANTHROPIC_API_KEY` in your environment (or a `.env` file)

## Setup

```bash
cd mcp-client

# install dependencies
uv sync          # with uv
# or
pip install -e . # with pip
```

Create a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
python client.py <server_command> [server_args...]
```

### Examples

```bash
# Python MCP server
python client.py python my_server.py

# Node.js MCP server
python client.py node my_server.js

# Any executable MCP server
python client.py ./my-mcp-server --config config.json
```

## REPL Commands

| Command  | Description                          |
|----------|--------------------------------------|
| `/tools` | Refresh and display available tools  |
| `/clear` | Clear conversation history           |
| `/exit`  | Quit the client                      |

## Project Structure

```
mcp-client/
├── client.py        # Main client implementation
├── pyproject.toml   # Project metadata and dependencies
├── uv.lock          # Locked dependency versions
└── .env             # API keys (not committed)
```
