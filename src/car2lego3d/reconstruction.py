import subprocess
import sys
import types
from functools import partial
from pathlib import Path

from .common import ROOT, device_name, digest, model_lock, stage


def setup_source():
    spec = model_lock()["triposr_code"]
    target = ROOT / "external" / "TripoSR"
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        subprocess.run(["git", "clone", spec["url"], str(target)], check=True)
    subprocess.run(["git", "-C", str(target), "checkout", "--detach", spec["commit"]], check=True)
    return target


def marching_cubes(volume, level):
    """Match torchmcubes' reversed vertex coordinates; upstream reverses them back."""
    import numpy as np
    import torch
    from skimage.measure import marching_cubes as extract

    vertices, faces, _, _ = extract(volume.detach().float().cpu().numpy(), level=level)
    vertices = np.ascontiguousarray(vertices[:, [2, 1, 0]])
    return torch.from_numpy(vertices).to(volume.device), torch.from_numpy(faces.astype(np.int64)).to(volume.device)


def upstream_model():
    source = ROOT / "external" / "TripoSR"
    if not (source / "tsr" / "system.py").is_file():
        raise RuntimeError("TripoSR source missing. Run car2lego3d setup.")
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if commit != model_lock()["triposr_code"]["commit"]:
        raise RuntimeError("Unexpected TripoSR version; run car2lego3d setup to pin it.")
    sys.path.insert(0, str(source))
    # This is an explicit backend adapter, not a replacement reconstruction model.
    shim = types.ModuleType("torchmcubes")
    shim.marching_cubes = marching_cubes
    sys.modules["torchmcubes"] = shim
    from huggingface_hub import hf_hub_download
    from tsr.models.tokenizers import image as tokenizer
    tokenizer.hf_hub_download = partial(hf_hub_download, revision=model_lock()["dino_config"]["revision"])
    from tsr.system import TSR
    return TSR


def preprocess(source, directory, remove_background=True, foreground_ratio=0.85):
    import numpy as np
    import rembg
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(Image.open(source)).convert("RGBA")
    image.thumbnail((2048, 2048))
    has_alpha = image.getextrema()[3][0] < 255
    if remove_background and not has_alpha:
        image = rembg.remove(image, session=rembg.new_session("u2netp", providers=["CPUExecutionProvider"]))
    if remove_background or has_alpha:
        bbox = image.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
        if bbox is None:
            raise ValueError("Background removal found no foreground. Try --no-remove-bg.")
        image = image.crop(bbox)
        size = round(max(image.size) / foreground_ratio)
        canvas = Image.new("RGBA", (size, size))
        canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
        image = canvas
    image.save(directory / "foreground.png")
    array = np.asarray(image).astype(np.float32) / 255
    array = array[..., :3] * array[..., 3:] + 0.5 * (1 - array[..., 3:])
    output = Image.fromarray((array * 255).astype(np.uint8))
    output.save(directory / "input.png")
    return output


def reconstruct(source, directory, resolution=128, chunk_size=4096, device="auto", remove_background=True):
    import torch
    from huggingface_hub import snapshot_download

    source, directory = Path(source), Path(directory)
    device = device_name(device)
    with stage(directory, "reconstruction", {"image": source.name, "sha256": digest(source),
                    "resolution": resolution, "chunk_size": chunk_size, "device": device,
                    "remove_background": remove_background, "foreground_ratio": 0.85}) as record:
        image = preprocess(source, directory, remove_background)
        spec = model_lock()["triposr_weights"]
        weights = snapshot_download(spec["repo"], revision=spec["revision"], allow_patterns=["config.yaml", "model.ckpt"])
        TSR = upstream_model()
        # Keep upstream float32 inference; only marching cubes runs on the CPU.
        model = TSR.from_pretrained(weights, config_name="config.yaml", weight_name="model.ckpt")
        model.renderer.set_chunk_size(chunk_size)
        model.to(device).eval()
        if device.startswith("cuda"):
            torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            codes = model([image], device=device)
            mesh = model.extract_mesh(codes, has_vertex_color=True, resolution=resolution)[0]
        mesh.fix_normals()
        if len(mesh.vertices) == 0:
            raise RuntimeError("Reconstruction produced an empty mesh.")
        mesh.export(directory / "mesh.glb")
        mesh.export(directory / "mesh.obj")
        record.update(vertices=len(mesh.vertices), faces=len(mesh.faces), watertight=bool(mesh.is_watertight),
                      bounds=mesh.bounds.tolist(), backend="TripoSR + scikit-image marching cubes",
                      outputs={name: digest(directory / name) for name in ("input.png", "mesh.glb", "mesh.obj")})
        if device.startswith("cuda"):
            record["peak_gpu_allocated_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 2)
        del codes, model
        if device.startswith("cuda"):
            torch.cuda.empty_cache()
    return directory / "mesh.glb"
