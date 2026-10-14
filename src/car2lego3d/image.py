from pathlib import Path

from .common import device_name, digest, model_lock, stage


def generate(prompt, directory, seed=42, steps=4, device="auto", vehicle_spec=None):
    import torch
    from diffusers import AutoPipelineForText2Image

    directory = Path(directory)
    device = device_name(device)
    spec = model_lock()["sd_turbo"]
    composed = (f"Product photo of {prompt}. Single complete car, three quarter view, "
                "isolated on white, entire vehicle visible, no text.")
    specifications = None
    if vehicle_spec is not None:
        from .vehicle import load_spec, prompt_hint, spec_record
        specifications = load_spec(vehicle_spec)
        composed += " " + prompt_hint(specifications)
    with stage(directory, "image", {"prompt": prompt, "composed_prompt": composed,
                                    "seed": seed, "steps": steps, "device": device}) as record:
        if specifications is not None:
            record.update(vehicle_spec=spec_record(vehicle_spec), specifications=specifications,
                          physical_proportions_guaranteed=False)
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
