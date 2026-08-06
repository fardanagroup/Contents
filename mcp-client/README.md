# MCP Client

A small terminal MCP client with a refreshed, color-coded console experience.

## Highlights

- Styled banner and clearer section separators
- Distinct colors for prompts, assistant replies, tool calls, and tool output
- Built-in `/tools`, `/clear`, and `/exit` commands
- Reads `ANTHROPIC_API_KEY` from your environment or `.env`
- Uses `claude-3-5-sonnet-latest` by default and lets you override it with `ANTHROPIC_MODEL`

## Setup

```bash
cd mcp-client
python -m pip install -e .
```

## Usage

```bash
python client.py <server_command> [server_args...]
```

Example:

```bash
python client.py python /path/to/server.py
```