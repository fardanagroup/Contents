# mcp-client

A minimal, interactive MCP (Model Context Protocol) client powered by
[Anthropic Claude](https://www.anthropic.com/). Connect it to any MCP server
and get a Claude-backed chat loop with full access to the server's tools.

---

## Features

- Supports Python (`.py`) and Node.js (`.js`) MCP server scripts.
- Automatic tool discovery — lists every tool the server exposes at startup.
- Agentic loop — Claude can call tools multiple times per turn until it has a
  final answer.
- Simple REPL interface; type `quit` or `exit` to stop.

---

## Requirements

| Requirement | Version |
|---|---|
| Python | ≥ 3.11 |
| [uv](https://github.com/astral-sh/uv) | latest |
| Anthropic API key | — |

---

## Setup

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd mcp-client
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and set your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Install dependencies with uv

```bash
uv sync
```

---

## Usage

```bash
uv run client.py <path_to_mcp_server_script>
```

### Examples

```bash
# Python MCP server
uv run client.py server.py

# Node.js MCP server
uv run client.py /path/to/server.js
```

The client will:

1. Launch the server as a subprocess over stdio.
2. Print the tools the server exposes.
3. Open an interactive prompt where every message is sent to Claude together
   with those tools.
4. Execute any tool calls Claude makes via the MCP server and feed the results
   back to Claude automatically.

---

## Thesis review use-case

This client was built to support academic document review (skripsi FEB
Universitas Airlangga). Pair it with an MCP server that exposes file-reading
tools (e.g. the
[MCP filesystem server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem))
to let Claude:

- Read `.docx` thesis chapters and style guides.
- Diagnose formatting deviations against the *Buku Pedoman Penulisan Skripsi
  FEB Unair*.
- Flag Mendeley citation objects without modifying them.
- Generate a ranked list of formatting issues (fatal → minor) with specific
  locations and corrective instructions.

> **Important – Mendeley citations**: never ask Claude to rewrite or move
> citation text; always instruct it to mark positions with
> `[SITASI MENDELEY — JANGAN DISENTUH]` and revise only the surrounding text.

---

## Project structure

```
mcp-client/
├── client.py        # MCP client (this file)
├── pyproject.toml   # Project metadata and dependencies
├── .env.example     # API key template
├── .env             # Your secrets (git-ignored)
└── README.md        # This file
```

---

## License

MIT
