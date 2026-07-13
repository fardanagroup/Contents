# mcp-client

A Python client that calls the Claude Messages API with a remote MCP server
attached via the [MCP connector (beta)](https://docs.anthropic.com/en/docs/agents-and-tools/mcp).

Anthropic handles the MCP connection server-side, so there is nothing extra
to run locally — just point the client at your MCP server URL.

## Setup

```bash
cp .env.example .env
# edit .env and fill in your credentials
uv sync
```

## Usage

**From Python:**

```python
from client import ClaudeMcpService

result = ClaudeMcpService().call("What tools can you use?")
print(result.text)
```

**From the command line:**

```bash
ANTHROPIC_API_KEY=sk-... \
MCP_SERVER_URL=https://your-mcp-server/sse \
uv run python client.py "What tools can you use?"
```

**With an allowed-tools allowlist:**

```python
svc = ClaudeMcpService(allowed_tools=["read_file", "list_directory"])
result = svc.call("List the files in the current directory.")
```

## Configuration

| Variable           | Required | Description                                         |
|--------------------|----------|-----------------------------------------------------|
| `ANTHROPIC_API_KEY` | Yes     | Your Anthropic API key                              |
| `MCP_SERVER_URL`   | Yes      | Remote MCP server endpoint (Streamable HTTP / SSE)  |
| `MCP_SERVER_TOKEN` | No       | Bearer token forwarded to the MCP server            |

## Tests

```bash
uv run python -m pytest tests/
```
