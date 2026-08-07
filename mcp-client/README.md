# mcp-client

An interactive [MCP](https://modelcontextprotocol.io) client backed by Claude.
It launches a single MCP server over stdio, exposes that server's tools to
Claude, and runs a chat loop where Claude can call the tools to answer your
questions.

## Setup

```bash
uv sync
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

## Usage

Point the client at an MCP server. The server can be a Python script or any
command that speaks MCP over stdio:

```bash
# A local Python MCP server
uv run client.py path/to/server.py

# An npm-published MCP server
uv run client.py npx -y @modelcontextprotocol/server-filesystem /tmp
```

Then type queries at the `>` prompt. Type `quit` (or Ctrl-D) to exit.

## Configuration

Set these in `.env` (all optional except the API key):

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Required. Your Anthropic API key. |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` | Model used for the chat loop. |
| `ANTHROPIC_MAX_TOKENS` | `1000` | Max tokens per response. |

## How it works

1. `connect()` starts the server process and initializes an MCP session.
2. Each query is sent to Claude along with the server's tool definitions.
3. When Claude requests a tool, the client calls it via MCP, feeds the result
   back, and loops until Claude produces a final text answer.
