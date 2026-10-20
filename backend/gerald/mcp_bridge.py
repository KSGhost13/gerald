"""Stdio MCP bridge: Codex desktop and CLI control the same dashboard server."""
import os
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('GERALD')
BASE = 'http://127.0.0.1:' + os.getenv('GERALD_PORT', '8765')

async def request(method, path, body=None):
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        response = await client.request(method, BASE + '/api' + path, json=body)
        response.raise_for_status()
        return response.json()

@mcp.tool()
async def gerald_state() -> dict:
    """Read agents, workflow connections, mission status, public outputs and recent events."""
    return await request('GET', '/state')

@mcp.tool()
async def gerald_integrations() -> dict:
    """Discover configured Ollama servers/models and installed Codex/Ollama CLIs."""
    return await request('GET', '/integrations')

@mcp.tool()
async def gerald_forge(name: str, role: str, directive: str, provider: str = 'ollama', model: str = '', tools: list[str] | None = None) -> dict:
    """Create an agent. Providers: ollama, ollama-cli, codex, codex-ollama, anthropic.
    Tools: workspace_read, workspace_write, system_metrics. Automatically connects GERALD to the new worker.
    """
    return await request('POST', '/agents', {'name': name, 'role': role, 'directive': directive,
        'provider': provider, 'model': model, 'tools': tools or []})

@mcp.tool()
async def gerald_mission(prompt: str, agent_id: str = 'gerald') -> dict:
    """Submit a goal asynchronously. Use gerald_state to follow its job ID and outputs."""
    return await request('POST', '/goals', {'prompt': prompt, 'agent_id': agent_id})

@mcp.tool()
async def gerald_control(agent_id: str, action: str) -> dict:
    """Control a worker: pause (finish current work), resume, abort (cancel work), delete."""
    return await request('POST', f'/agents/{agent_id}/{action}')

@mcp.tool()
async def gerald_route(edges: list[dict[str, str]]) -> dict:
    """Atomically replace graph edges, each with source and target IDs. Cycles are rejected."""
    return await request('PUT', '/graph', {'edges': edges})

@mcp.tool()
async def gerald_mode(mode: str) -> dict:
    """Set local or cloud execution mode for future tasks."""
    return await request('PUT', '/mode', {'mode': mode})

if __name__ == '__main__':
    mcp.run(transport='stdio')
