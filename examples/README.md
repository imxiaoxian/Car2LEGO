# Measured Examples

- `f40-physical/`: full prompt-to-Studio run with a sourced Ferrari F40 physical
  profile, raw and calibrated TripoSR meshes, native car parts, dimensions report
  and `.io` archive. Native renderer preview uses real part geometry. Door/glass
  dimensions remain unknown; appearance, collision and physical assembly are
  not accepted. See `00-vehicle/spec.json` for provenance and unknown fields.
- `f40/`: SD-Turbo seed 42 generated image, actual TripoSR reconstruction at
  resolution 128, and mesh-derived color plates at 32 studs. Model inputs,
  hashes, timings and package versions are recorded in JSON beside each stage.
- `f40/03-lego/native-ldraw.png`: real LDraw part geometry rendered by Blender
  through ldraw-mcp. This is different from the cuboid `lego-preview.png`.
  The library recognizes every part ID and color; see `library-bom.json`.
  Rendering is not collision, Studio GUI, insertion or physical validation.
- `f40-uniform-control/`: the same reconstructed mesh with LDraw color 4 forced
  everywhere. This isolates geometry and packing from vertex color noise.
- `upstream-chair/`: actual CPU inference at resolution 64 from the upstream
  TripoSR `examples/chair.png` image. Upstream example attribution: Tripo AI &
  Stability AI, MIT, pinned commit in `models.lock.json`.

These are generated artifacts, not handcrafted substitute meshes. None of them
is certified physically buildable. The F40 image and unseen geometry are model
predictions; they do not establish exact Ferrari F40 dimensions or appearance.
