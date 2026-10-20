"""Test the registered stdio bridge using the official MCP client."""
import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    root = Path(__file__).resolve().parents[1]
    parameters = StdioServerParameters(command=sys.executable, args=[str(root / 'backend/gerald/mcp_bridge.py')])
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = [tool.name for tool in listed.tools]
            assert len(names) == 13, names
            result = await session.call_tool('gerald_state', {})
            assert not result.isError, result
            print('MCP handshake verified. Thirteen tools discovered; live dashboard state retrieved.')
            print(', '.join(names))

asyncio.run(main())
