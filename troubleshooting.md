# Troubleshooting

This document summarizes common issues encountered with this MCP + LangChain client and how they were resolved.

---

## Python environment and imports

### `Import "langchain_mcp_adapters..." could not be resolved`

**Cause:** The IDE and `python` on your PATH point at the project `.venv`, but packages were installed with a different `pip` (e.g. Anaconda), so `langchain-mcp-adapters` was not in the same environment.

**Fix:**

- Install deps into the same interpreter you run:  
  `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`  
  (or `uv sync` from the repo root).
- In the editor, choose **Python: Select Interpreter** → this project’s `.venv`.

---

## LangChain MCP adapters API

### `TypeError: MultiServerMCPClient.__init__() got an unexpected keyword argument 'servers'`

**Cause:** In current `langchain-mcp-adapters`, the mapping is passed as **`connections`** (positional or keyword), not `servers`.

**Fix:** Use `MultiServerMCPClient(connections)` or `MultiServerMCPClient(connections=my_dict)`.

---

## MCP stdio server process

### `McpError: Connection closed` during `get_tools()` / `initialize()`

**Typical causes:**

1. **Wrong script path** — The stdio command must run the real MCP server entrypoint (e.g. `main.py` that calls `mcp.run()`), not a client script or a non‑existent file. If the subprocess exits immediately, the client sees “connection closed.”
2. **Placeholder paths** — Copy‑pasting `...\...` literally instead of full paths breaks `uv run` / `python`.
3. **Stdout pollution** — Some servers print banners to stdout; in strict setups that can interfere with the JSON‑RPC stream (worth checking if handshakes are flaky).

**Fix:** Confirm the `command` / `args` run the server manually in a terminal; use absolute paths.

### “The server isn’t starting” (stdio)

**What’s normal:** For **stdio** transport, the server is a **child process** with no separate terminal and usually no “listening on port” message. It runs for the lifetime of the client operation. A successful `get_tools()` proves the subprocess did start and complete the MCP handshake.

---

## LangChain + Anthropic + tools

### `ValidationError` for `ChatAnthropic` — `model_name` / `model` required

**Cause:** `ChatAnthropic` requires a **model** id (e.g. `claude-sonnet-4-20250514`), not only `api_key`.

**Fix:** Pass `model=...` (or set `ANTHROPIC_MODEL` in `.env`). See `.env.example`.

### Model returns `tool_calls` but no real answer (e.g. no numeric result)

**Cause:** `bind_tools()` only registers tools. A single `ainvoke()` may stop at “I will call multiply” without **executing** tools.

**Fix:** Run a loop: append the model message; for each `tool_call`, `await tool.ainvoke(...)`, append **`ToolMessage(..., tool_call_id=tc["id"])`**, then call the model again until there are no tool calls. `client1.py` implements this pattern.

### `ToolMessage` — `KeyError: 'tool_call_id'`

**Cause:** `ToolMessage` must include **`tool_call_id`** matching the model’s tool call. Using **`tool_name=`** alone is invalid for this flow.

**Fix:** `ToolMessage(content=..., tool_call_id=tc["id"])`.

### `bind_tools` received a **dict** of tools

**Cause:** `bind_tools` expects a **sequence** of tools. Iterating a `dict` iterates **keys** (strings), not tool objects.

**Fix:** Pass the list from `get_tools()`, e.g. `bind_tools(tools)`.

---

## Multiple MCP servers

### Writes “succeed” in chat but **list / query** doesn’t show new data

**Cause:** With several servers, **duplicate tool names** (e.g. two servers both expose `add`) mean only one survives in `tool_by_name = {t.name: t for t in tools}`. The model may appear to add an expense while actually invoking the **wrong** server’s tool.

**Fix:** Use `MultiServerMCPClient(..., tool_name_prefix=True)` so tools are prefixed (e.g. `servername_toolname`). See `client1.py`.

### Hosted FastMCP / streamable HTTP **`401 Unauthorized`**

**Cause:** The URL requires authentication; `get_tools()` fails for that server and, because servers are loaded together, the whole call can fail.

**Fix:** Supply a bearer token (e.g. `Authorization: Bearer ...`) in the connection `headers`, usually from `REMOTE_EXPENSE_MCP_TOKEN` in `.env`. This repo skips adding the remote server if the token is missing so local servers still work.

---

## Manim and slow startup

### `python client1.py` prints nothing for a long time

**Cause:** `await client.get_tools()` starts **every** configured stdio server. **Manim** MCP often imports heavily and can take minutes before the first line appears.

**Fix:**

- Set **`MCP_ENABLE_MANIM=0`** in `.env` when you only need math/expense (faster).
- Set **`MCP_ENABLE_MANIM=1`** when the prompt needs Manim tools.
- Progress messages in `client1.py` indicate load phase; use **`MCP_CLIENT_DEBUG=1`** to log each tool invocation.

### Model says it has **no Manim tools**

**Cause:** `MCP_ENABLE_MANIM` is off or Manim failed to load, but the prompt still asks for Manim.

**Fix:** Enable Manim in `.env` and ensure paths to `python` / `manim_server.py` / `MANIM_EXECUTABLE` are correct.

---

## Invalid Python / config pasted from JSON or Cursor

### `NameError: name 'null' is not defined`

**Cause:** JSON uses `null`; Python uses **`None`**. Cursor MCP config blocks sometimes include extra keys (`type`, `keep_alive`, …) that are not part of `langchain_mcp_adapters` `StdioConnection`.

**Fix:** Use only supported keys (`transport`, `command`, `args`, `env`, etc.) and valid Python literals.

---

## Interrupting a run

### `UnboundLocalError: ... 'call_tool_result'` in `langchain_mcp_adapters` after **Ctrl+C**

**Cause:** Cancelling a tool call while a per‑call MCP session is tearing down can hit a bug path in older adapter versions where `call_tool_result` is returned without being set.

**Fix:** Avoid interrupting mid‑tool when possible. A local patch may initialize `call_tool_result` and raise a clear `RuntimeError` if the call produced no result; upstream may fix this in a newer `langchain-mcp-adapters` release. Re‑installing the venv can remove a local patch.

`client1.py` catches **KeyboardInterrupt** at the top level for a cleaner exit (still exit code 130).

---

## Git and GitHub

### Push rejected: **Push cannot contain secrets** (push protection)

**Cause:** `.env` (or other files) with API keys was committed.

**Fix:**

- Never commit `.env` — use `.gitignore` (this repo includes it) and **`.env.example`** for variable names only.
- Remove `.env` from history before pushing (`git reset` / rewrite commits), then **rotate** any key that was ever committed.
- After fixing history, push again; protection should pass if no secrets remain in reachable commits.

---

## Quick reference: environment variables

See **`.env.example`**. Common variables:

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `ANTHROPIC_MODEL` | Model id |
| `REMOTE_EXPENSE_MCP_URL` | Streamable HTTP MCP URL (optional) |
| `REMOTE_EXPENSE_MCP_TOKEN` | Bearer token for hosted MCP (optional) |
| `MCP_ENABLE_MANIM` | `1` / `0` — include Manim server in `get_tools()` |
| `MCP_CLIENT_DEBUG` | `1` — print each tool call and result |

---

## Official docs

- [LangChain MCP (Python)](https://docs.langchain.com/oss/python/langchain/mcp)
- [GitHub: push protection](https://docs.github.com/code-security/secret-scanning/working-with-secret-scanning-and-push-protection/working-with-push-protection-from-the-command-line)
