"""Smoke-test the configured LDraw MCP over stdio in its isolated environment.

Run with the ldraw-venv Python. No backend credentials are read.
"""
import argparse
import asyncio
import base64
from collections import Counter
import json
import os
from pathlib import Path
import tomllib

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def check(output: Path, render: bool) -> None:
    config = tomllib.loads((Path.home() / ".codex/config.toml").read_text(encoding="utf-8"))
    server = config["mcp_servers"]["ldraw"]
    params = StdioServerParameters(command=server["command"], args=server.get("args", []),
                                   env=server.get("env", {}))
    output.mkdir(parents=True, exist_ok=True)
    project = Path(__file__).resolve().parents[2]
    report = {"transport": "stdio", "samples": [], "render": "not_requested"}
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=180) as client:
            init = await client.initialize()
            print("MCP initialized", flush=True)
            report["server"] = init.server_info.model_dump()
            report["tools"] = [tool.name for tool in (await client.list_tools()).tools]
            for name, args in [("check_renderer", {}), ("lookup_color", {"query": "4"}),
                               ("search_parts", {"query": "hinge", "limit": 8})]:
                result = await client.call_tool(name, args)
                print(f"{name} returned", flush=True)
                report[name] = result.model_dump(mode="json")
                if result.is_error:
                    raise RuntimeError(f"{name}: {result.content}")
            samples = json.loads((project / "backend/storage/f40_samples.json").read_text())
            for sample in samples["samples"]:
                model = project / "backend/storage" / sample["id"] / "model.mpd"
                result = await client.call_tool("bill_of_materials", {"path": str(model)})
                print(f"BOM {sample['scale']} returned", flush=True)
                if result.is_error:
                    raise RuntimeError(str(result.content))
                data = result.structured_content
                if data is None:
                    data = json.loads(result.content[0].text)
                (output / f"bom-{sample['id']}.json").write_text(
                    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                total = data["total_parts"]
                scene = json.loads((model.parent / "scene.json").read_text(encoding="utf-8"))
                expected = Counter((p["part_num"].lower(), p["color_id"]) for p in scene["parts"])
                actual = Counter({(row["part"].lower(), row["color_code"]): row["quantity"]
                                  for row in data["rows"]})
                report["samples"].append({"id": sample["id"], "scale": sample["scale"],
                                          "expected": sample["parts"], "actual": total,
                                          "matched": total == sample["parts"] and expected == actual,
                                          "parts_and_colors_matched": expected == actual})
                assert total == sample["parts"] and expected == actual, "independent MPD BOM differs from scene"
            if render:
                # Transparency and internal colours alongside two connected bricks.
                text = ("0 Renderer smoke test\n"
                        "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
                        "1 14 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
                        "1 40 100 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n")
                result = await client.call_tool("render_ldraw_text", {
                    "ldr": text, "azimuths": "-60,120", "resolution": 320, "samples": 8})
                if result.is_error:
                    raise RuntimeError(str(result.content))
                images = [block for block in result.content if block.type == "image"]
                assert len(images) == 1, "renderer did not return an image"
                (output / "renderer-smoke.png").write_bytes(base64.b64decode(images[0].data))
                report["render"] = "passed"
    (output / "mcp-check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    print(json.dumps({"server": report["server"], "tools": report["tools"],
                      "samples": report["samples"], "render": report["render"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] /
                        "storage/tool_research/validation")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    os.environ.setdefault("PYTHONUTF8", "1")
    asyncio.run(check(args.output.resolve(), args.render))
