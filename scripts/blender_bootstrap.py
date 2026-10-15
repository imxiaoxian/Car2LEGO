"""Load the pinned addon in this Blender session without changing user preferences."""
import importlib.util
import os
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
addon, port = args[0], int(args[1])
os.environ["BLENDER_MCP_DISABLE_TELEMETRY"] = "true"
spec = importlib.util.spec_from_file_location("car2lego_blender_addon", addon)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.register()
bpy.context.scene.blendermcp_auto_start_server = False
server = module.BlenderMCPServer(host="127.0.0.1", port=port)
bpy.types.blendermcp_server = server
server.start()
print("CAR2LEGO_BLENDER_READY", port, flush=True)
