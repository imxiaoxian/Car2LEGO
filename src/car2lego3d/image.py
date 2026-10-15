from pathlib import Path
import re

from .common import device_name, digest, model_lock, stage


def compose_prompt(prompt, specifications=None):
    from .coupe import styling
    from .suv import styling as suv_styling
    detail = ""
    if styling(specifications) == "bmw-m4-g82":
        detail = " G82 generation, tall vertical twin kidney grille, slim headlights, black roof."
    if suv_styling(specifications):
        # SD-Turbo predates For Me; the manufacturer identifies its shared Eletre exterior.
        prompt = re.sub(r"Lotus\s+For\s*Me", "Lotus Eletre", prompt, flags=re.IGNORECASE)
        detail = " Four doors, black roof, slim headlights."
    composed = (f"Product photo of {prompt}.{detail} Full car, front three quarter view, "
                "white studio background, entire vehicle visible, no text.")
    if specifications is not None:
        from .vehicle import prompt_hint
        composed += " " + prompt_hint(specifications)
    return composed


def generate(prompt, directory, seed=42, steps=4, device="auto", vehicle_spec=None,
             provider="gpt", reference_image=None):
    if provider == "gpt":
        from .gpt_reference import generate as generate_reference
        return generate_reference(prompt, directory, vehicle_spec, reference_image)
    if reference_image:
        raise ValueError("Reference images currently require the GPT provider.")
    return generate_sd_turbo(prompt, directory, seed, steps, device, vehicle_spec)


def generate_sd_turbo(prompt, directory, seed=42, steps=4, device="auto", vehicle_spec=None):
    import torch
    from diffusers import AutoPipelineForText2Image

    directory = Path(directory)
    device = device_name(device)
    spec = model_lock()["sd_turbo"]
    specifications = None
    if vehicle_spec is not None:
        from .vehicle import load_spec, spec_record
        specifications = load_spec(vehicle_spec)
    composed = compose_prompt(prompt, specifications)
    with stage(directory, "image", {"prompt": prompt, "composed_prompt": composed,
                                    "seed": seed, "steps": steps, "device": device}) as record:
        if specifications is not None:
            record.update(vehicle_spec=spec_record(vehicle_spec), specifications=specifications,
                          physical_proportions_guaranteed=False)
            from .suv import styling as suv_styling
            if suv_styling(specifications):
                record["identity_proxy"] = {"name": "Lotus Eletre", "exact_identity_guaranteed": False,
                    "reason": "SD-Turbo predates For Me; published exterior shares the Eletre design.",
                    "source": "https://www.autohome.com.cn/news/202603/1313213.html"}
        pipeline = AutoPipelineForText2Image.from_pretrained(
            spec["repo"], revision=spec["revision"], torch_dtype=torch.float16 if device.startswith("cuda") else torch.float32,
            variant="fp16" if device.startswith("cuda") else None,
            use_safetensors=True,
        ).to(device)
        pipeline.enable_attention_slicing()
        token_count = len(pipeline.tokenizer(composed, truncation=False)["input_ids"])
        record.update(prompt_token_count=token_count, prompt_token_limit=pipeline.tokenizer.model_max_length,
                      prompt_truncated=False)
        if token_count > pipeline.tokenizer.model_max_length:
            raise ValueError(f"Image prompt requires {token_count} tokens; limit is "
                             f"{pipeline.tokenizer.model_max_length}. Shorten --prompt.")
        if device.startswith("cuda"):
            torch.cuda.reset_peak_memory_stats()
        image = pipeline(prompt=composed, num_inference_steps=steps, guidance_scale=0.0,
                         height=512, width=512, generator=torch.Generator(device=device).manual_seed(seed)).images[0]
        output = directory / "reference.png"
        image.save(output)
        record.update(output=output.name, sha256=digest(output), size=list(image.size),
                      license="SD-Turbo model license applies; see THIRD_PARTY_NOTICES.md")
        if device.startswith("cuda"):
            record["peak_gpu_allocated_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 2)
        del pipeline
        if device.startswith("cuda"):
            torch.cuda.empty_cache()
    return output
