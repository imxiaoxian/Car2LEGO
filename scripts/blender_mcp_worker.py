"""One real MCP stdio tool call to the pinned upstream Blender server."""
import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args):
    request = json.loads(args.input.read_text(encoding="utf-8"))
    environment = {**os.environ, "PYTHONPATH": str(args.source / "src"),
        "BLENDER_HOST": "127.0.0.1", "BLENDER_PORT": str(args.port),
        "CAR2LEGO_MCP_TIMEOUT": str(args.timeout),
        "BLENDER_MCP_DISABLE_TELEMETRY": "true", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
    params = StdioServerParameters(command=sys.executable,
        args=["-B", str(Path(__file__).with_name("blender_mcp_server.py"))], env=environment)
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=args.timeout + 15)) as session:
            initialized = await session.initialize()
            result = await session.call_tool(request["tool"], request.get("arguments", {}))
            output = dict(server=initialized.model_dump(mode="json"), result=result.model_dump(mode="json"))
            args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
            if result.isError:
                raise RuntimeError("Blender MCP tool failed; inspect response JSON")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    asyncio.run(run(parser.parse_args()))
