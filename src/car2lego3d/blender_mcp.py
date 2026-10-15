"""GPT vision-directed Blender modelling over the upstream MCP server and addon."""
import ast
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import shutil

from .common import ROOT, digest, model_lock, stage, write_json
from .dialogue import ask_json, image_content, settings
from .gpt_reference import configuration
from .multiview import load_views
from .vehicle import load_spec, spec_record


MODEL_TIMEOUT = 180
MCP_TIMEOUT = 600


PROMPT = """You are a senior automotive Blender modeller. Build an accurate detailed smooth car from ALL
four labelled elevation images and the overview. This is a 3D reconstruction experiment, NOT a LEGO model.
Return only JSON: {"analysis": "concise visual analysis and modelling plan", "code": "complete bpy script"}.
Script runs via Blender MCP execute_blender_code in Blender 4.5. Use only bpy, math, mathutils, random.
No filesystem, network, shell, addon installation, file loading or saving. Host code handles export/render.
Clear all scene objects before building. Units are METRES; full-size coordinates. X increases from FRONT
bumper (x=0) to REAR bumper (x=length); Y left/right centred at 0; Z up, tyre ground contact z=0.
Use vehicle specs for length, body width excluding mirrors, height, wheelbase, tyres and axle positions.
The supplied specification snapshot takes precedence over conflicting dimensions in the image brief.
Values are model estimates; prioritize image geometry for low confidence details while retaining core size.
Roof/cabin MUST have a shaped fastback/SUV profile if shown. Avoid generic boxes and faceted toy shapes.
Create a continuous curved body using dense longitudinal cross-section lofts with shoulder, beltline,
sill, bonnet and fender surfaces. Use real wheel-arch cuts (EXACT boolean or purpose-built topology),
body depth, underbody and connected shell. Do NOT use a cube as final main body. No floating broad panels.
Separate named body, roof, windshield, side windows, rear glass, pillars, four tyres/rims/spokes,
headlamps, rear light bar, intakes/grilles, rocker panels, door seams, handles, mirrors, spoiler as applicable.
Name four tyre objects tyre_front_left, tyre_front_right, tyre_rear_left, tyre_rear_right.
Tyre cylinders' axes are Y, wheels at front_overhang and front_overhang+wheelbase, authentic arch clearances.
Use procedural meshes/curves for narrow vehicle-specific light signatures and vents, not only primitives.
Glazing should be fitted TO the cabin surfaces, visually opaque dark glass (alpha=1, roughness .15),
not a giant dark box or an opaque panel hovering above body. Inspect opposite views for consistency.
Model the sharp styling identity and image colours. Good topology, smooth shading, bevels where appropriate.
Keep total evaluated triangles below 250000 and booleans limited. Don't subdivide Boolean result arbitrarily.
Materials use Principled BSDF Base Color/Metallic/Roughness. Emit lenses via Emission Color/Strength.
No text labels, ground plane, camera or light. The host adds a common render rig. No need to print vertices.
"""


def validate_code(code):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [n.name.split(".")[0] for n in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            if any(n not in {"bpy", "math", "mathutils", "random"} for n in names):
                raise ValueError("Generated model imports outside Blender/math are unsupported")
        if isinstance(node, ast.Name) and node.id in {"open", "exec", "eval", "compile", "__import__"}:
            raise ValueError("Generated modelling code cannot perform file or dynamic-code operations")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in {
                "save_as_mainfile", "open_mainfile", "read_factory_settings", "quit_blender"}):
            raise ValueError("Scene lifecycle is managed by the host")
    return code


def upstream():
    spec = model_lock()["blender_mcp_code"]
    source = ROOT / "external/mcp-for-blender"
    if not source.exists():
        subprocess.run(["git", "clone", spec["url"], str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "checkout", "--detach", spec["commit"]], check=True)
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if commit != spec["commit"]:
        raise ValueError("Blender MCP checkout differs from the pinned commit")
    return source


def call(tool, arguments, directory, name, port=9877):
    from dotenv import dotenv_values
    source, python = configuration()
    local = dotenv_values(ROOT / ".env")
    python = os.environ.get("CAR2LEGO_MCP_PYTHON") or local.get("CAR2LEGO_MCP_PYTHON") or str(python)
    request, response = directory / f"{name}-mcp-request.json", directory / f"{name}-mcp-response.json"
    write_json(request, dict(tool=tool, arguments=arguments))
    timeout = float(os.environ.get("CAR2LEGO_MCP_TIMEOUT")
                   or local.get("CAR2LEGO_MCP_TIMEOUT") or MCP_TIMEOUT)
    if timeout <= 0:
        raise ValueError("CAR2LEGO_MCP_TIMEOUT must be positive")
    result = subprocess.run([python, "-B", str(ROOT / "scripts/blender_mcp_worker.py"),
        "--input", str(request), "--output", str(response), "--source", str(upstream()), "--port", str(port),
        "--timeout", str(timeout)],
        capture_output=True, cwd=ROOT, timeout=timeout + 30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
    (directory / f"{name}-mcp.log").write_bytes(result.stdout + result.stderr)
    if result.returncode:
        details = response.read_text(encoding="utf-8") if response.is_file() else result.stderr.decode(errors="replace")
        raise RuntimeError(details[-12000:])
    data = json.loads(response.read_text(encoding="utf-8"))
    texts = [c.get("text", "") for c in data["result"]["content"] if c["type"] == "text"]
    text = "\n".join(texts)
    if text.startswith("Error") or "Error executing" in text:
        raise RuntimeError(text)
    return data


class BlenderSession:
    def __init__(self, directory, port=9877):
        self.directory, self.port = Path(directory), port

    def __enter__(self):
        from dotenv import dotenv_values
        local = dotenv_values(ROOT / ".env")
        binary = os.environ.get("CAR2LEGO_BLENDER") or local.get("CAR2LEGO_BLENDER")
        if not binary:
            source, _ = configuration()
            binary = source / "backend/storage/tool_research/blender-4.5.14-windows-x64/blender.exe"
        self.directory.mkdir(parents=True, exist_ok=True)
        config_directory = self.directory / "blender-user-config"
        config_directory.mkdir(exist_ok=True)
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                raise ValueError(f"Experiment Blender port {self.port} is already in use")
        self.log = (self.directory / "blender.log").open("wb")
        startup = None
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 0
        self.process = subprocess.Popen([str(binary), "--factory-startup", "--python",
            str(ROOT / "scripts/blender_bootstrap.py"), "--", str(upstream() / "addon.py"), str(self.port)],
            cwd=ROOT, stdout=self.log, stderr=subprocess.STDOUT, startupinfo=startup,
            env={**os.environ, "BLENDER_MCP_DISABLE_TELEMETRY": "true",
                 "BLENDER_USER_CONFIG": str(config_directory.resolve())})
        for _ in range(120):
            if self.process.poll() is not None:
                self.log.close()
                raise RuntimeError("Blender startup failed; inspect blender.log")
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                    return self
            time.sleep(.5)
        self.__exit__(None, None, None)
        raise TimeoutError("Blender MCP startup timed out")

    def execute(self, code, name):
        return call("execute_blender_code", {"code": code, "user_prompt": "Car2LEGO multiview modelling experiment"},
                    self.directory, name, self.port)

    def __exit__(self, *args):
        self.process.terminate()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.log.close()


def render_code(directory, export=True):
    template = (ROOT / "scripts/blender_export_render.py").read_text(encoding="utf-8")
    return "OUTPUT_DIRECTORY = " + repr(str(Path(directory).resolve())) + "\nEXPORT = " + repr(export) + "\n" + template


def modelling_model():
    return settings(model_key="CAR2LEGO_BLENDER_MODEL", default_model="gpt-6-astra")["model"]


def reconstruct(manifest_path, directory, vehicle_spec, review=True):
    if vehicle_spec is None:
        raise ValueError("GPT Blender modelling requires a physical specification snapshot")
    directory = Path(directory).resolve()
    manifest, paths = load_views(manifest_path)
    spec = load_spec(vehicle_spec)
    images = dict(paths)
    if (Path(manifest_path).parent / "reference.png").is_file():
        images["overview"] = Path(manifest_path).parent / "reference.png"
    model = modelling_model()
    inputs = dict(backend="gpt-blender", model=model, views=manifest["views"],
                  manifest_sha256=digest(manifest_path), vehicle_spec=spec_record(vehicle_spec))
    with stage(directory, "reconstruction", inputs) as record:
        user = [{"type": "text", "text": json.dumps({"vehicle": spec, "brief": manifest.get("brief")}, ensure_ascii=False)},
                *image_content(images)]
        messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": user}]
        response = ask_json(messages, directory, "model", max_tokens=24000, timeout=MODEL_TIMEOUT,
                            reuse_completed=True, model=model, stream=True)
        with BlenderSession(directory) as blender:
            for attempt in range(3):
                code = validate_code(response["code"])
                (directory / f"model-{attempt + 1}.py").write_text(code, encoding="utf-8")
                try:
                    blender.execute(code, f"model-{attempt + 1}")
                    break
                except RuntimeError as error:
                    if attempt == 2:
                        raise
                    messages += [{"role": "assistant", "content": json.dumps(response)},
                        {"role": "user", "content": "Execution failed. Return a corrected FULL script: " + str(error)[-7000:]}]
                    response = ask_json(messages, directory, f"repair-{attempt+1}", max_tokens=24000,
                                        timeout=MODEL_TIMEOUT, model=model, stream=True)
            blender.execute(render_code(directory), "export-render")
            if review:
                before = directory / "before-review"
                before.mkdir(exist_ok=True)
                for path in directory.iterdir():
                    if path.suffix in {".png", ".glb", ".obj", ".mtl", ".blend"} or path.name == "scene-metrics.json":
                        shutil.copyfile(path, before / path.name)
                feedback = ask_json([{"role": "system", "content": PROMPT + "\nReview the reference vs current renders. "
                    "Return JSON {analysis, code}; code is a corrective PATCH to the existing scene, not a fresh scene. "
                    "Do not clear all objects. If no concrete improvement is possible, code is an empty string."},
                    {"role": "user", "content": [{"type": "text", "text": "Vehicle specifications: " + json.dumps(spec)},
                        *image_content(images), *image_content({"CURRENT_" + v: directory / f"render-{v}.png"
                            for v in ("left", "front", "back", "three-quarter")}),
                        {"type": "text", "text": "Current script: " + response["code"]}]}],
                    directory, "visual-review", max_tokens=18000, timeout=MODEL_TIMEOUT, model=model, stream=True)
                if feedback.get("code", "").strip():
                    try:
                        blender.execute(validate_code(feedback["code"]), "visual-refine")
                        blender.execute(render_code(directory), "refined-export-render")
                    except (RuntimeError, ValueError) as error:
                        # Keep the saved successful pre-review scene if a patch failed midway.
                        write_json(directory / "review-failure.json", dict(error=str(error)))
                        for path in before.iterdir():
                            shutil.copyfile(path, directory / path.name)
                        blender.execute("import bpy\nbpy.ops.wm.open_mainfile(filepath=" + repr(str(directory / "model.blend")) + ")", "restore")
            record.update(analysis=response["analysis"], model=model,
                addon=dict(commit=model_lock()["blender_mcp_code"]["commit"], sha256=digest(upstream() / "addon.py")),
                vehicle_spec=spec_record(vehicle_spec), glb_units="metres", obj_units="mm",
                physical_measurement_verified=False, appearance_accepted=False,
                outputs={p.name: digest(p) for p in directory.iterdir() if p.suffix in {".glb", ".obj", ".blend", ".png"}})
    return directory / "calibrated.glb"
