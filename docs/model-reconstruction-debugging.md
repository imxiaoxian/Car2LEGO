# Blender Reconstruction Diagnostics

The reconstruction stage uses the four GPT elevation images and an estimated
vehicle specification with `gpt-6-astra`, executed through the pinned Blender MCP
addon. It exports a full-size smooth car, before LEGO part fitting.

## Changes

- Transient stream failures allow up to two fresh modelling requests within a
  shared elapsed-time budget. Failed events remain on disk; partial code is
  never executed. Only an authoritative completed response can be consumed.
- Progress snapshots update at most twice per second. Atomic JSON replacement
  retries brief Windows reader locks, while retaining the previous valid file
  on a persistent write denial.
- Doors require a common parent for panel, frame and moving glass. Parenting
  must preserve world transforms after the parent matrix is updated. Glass and
  frame share boundary coordinates; fixed quarter glass remains separate.
- Low-confidence cabin estimates yield to the reference silhouette. Core
  dimensions, axle placement and tyre specifications remain explicit priors.
- Closed meshes receive consistent outward normals before export and subsequent
  Boolean corrections. This prevents inverted shells from reversing differences.
- Measured scene diagnostics accompany the rendered views in visual review.
  A patch introducing a new failing check is rejected even when it fixes more
  existing failures. The prior scene is restored; rejected files are retained.

`scene-metrics.json` records evaluated world bounds, triangle counts, topology,
parent relationships, glass-to-own-frame distances, seam sampling, and glass-normal
visibility rays. Rays permit dividers belonging to the same door, so a legitimate window
frame does not become a false occlusion failure.

`model-quality.json` checks dimensions, tyre orientation and grounding, axle
placement, roof and door envelopes, assembly membership, glass contacts,
visibility, triangle budget and nonblank/unclipped rendered views. Open-wheel
and convertible policies use explicit body style. These are engineering
diagnostics against model estimates, not appearance or physical acceptance.

## Replay Without Image Generation

Use the experiment's Python environment and `PYTHONPATH=src`:

```powershell
python scripts/audit_blender_model.py --blend <scene.blend> --spec <spec.json> `
  --body-style sports_car --output <new-audit-directory>

python scripts/refine_blender_model.py --source <audited-directory> `
  --views <views.json> --spec <spec.json> --output <new-candidate-directory> `
  --focus "Describe a concrete geometry correction"
```

Audit calls no image or modelling API. Focused refinement calls Astra, preserves
the source directory and rejects any candidate with new geometry failures.
Both use a new isolated output directory and Blender MCP port 9878 by default.

## Local Countach Experiment

Evidence: `runs/countach-20261016/` (large artifacts are Git-ignored).

- `02-mesh-attempt1`: upstream terminal failure after about 907 seconds.
- `02-mesh`: interrupted upstream stream; no partial script consumed.
- `02-mesh-debug`: first completed script, with displaced doors; the visual
  patch exposed the inverted-shell Boolean failure.
- `02-mesh-v2`: a Windows progress-file replacement error interrupted generation.
- `02-mesh-v3`: complete multiview-to-Blender run. Initial script completed in
  129.032 seconds; visual review completed in 289.281 seconds. Six actual renders,
  `.blend`, GLB and millimetre OBJ were exported. All 53 diagnostics passed.
- `02-mesh-v3-audit`: an independent replay of the pre-review scene, using
  corrected visibility rays; 51 of 53 checks passed before intake correction.
- `02-mesh-focused`: an additional lamp/intake patch removed the evaluated body;
  it was rejected for `body_role`, and the source scene remained intact.

The previous selected scene was `02-mesh-v3/model.blend`. Its two moving side windows have
measured lower-edge anchor distances of at most approximately 4.4 mm from their
own door/frame surfaces. All dimensions are still model estimates. These runs
do not establish Studio compatibility, LEGO assembly quality, physical hinges,
or visual delivery acceptance. The experimental branch is not merged to main.

Validation after the changes: 290 backend tests passed, with 14 existing
matplotlib/pyparsing deprecation warnings. A regression test explicitly restores
the original scene when a patch fixes windows but introduces a body-width defect.

Streaming lifecycle reference:
https://developers.openai.com/api/docs/guides/streaming-responses

## Cabin, Nose And Tail Connections

The modelling and correction prompts now require shared boundary coordinates
at the cowl/pillars, nose/fenders/bumper and rear deck/buttresses/tail. Separate
transition meshes declare their actual contact-edge vertices in groups named
`join_<target car_role>`. Two rails meeting the same target use separate groups,
such as `join_body__a` and `join_body__b`; combining both rails also selects
internal cross-edges, which are not seams. `car_connection_region` identifies
`cabin`, `front` or `rear` for diagnostics. Windscreen and rear-glass upper/lower
boundary contacts are sampled automatically, independently of these declarations.

The exporter samples each declared source mesh edge at intervals of at most
10 mm and measures distance to evaluated target triangles. The diagnostic
threshold is 12 mm at full vehicle size. Empty seams, missing support geometry
and a gap between otherwise fitted endpoints all fail. A correction cannot
remove a previously passing seam family to suppress its check. These checks do
not establish tangency, absence of penetration, welded topology or watertight
union between separate parts; source groups are measured before modifiers.

Focused refinement now remeasures the saved source with the current exporter
before requesting a patch. Astra receives all six current views, the overview,
four GPT elevations, the scene inventory and available source scripts.

- `02-mesh-connections/baseline`: replay of v3. The new windscreen-bottom check
  found a 14.60 mm gap that the former 53 diagnostics did not cover.
- `02-mesh-connections`: first Astra patch closed the rear cabin corner and
  fitted the arch ribbons. Rejected for four new seam failures. Its front/rear
  groups combined both rails and sampled internal cross-edges.
- `02-mesh-connections-v2`: second Astra patch separated and fitted those rails,
  conformed thin lamp covers, shaped the quarter-glass/intake transition and
  fitted the rear dark valance. All 119 diagnostics passed, including 66 seam
  checks across all three regions. The maximum measured seam distance was
  2.53 mm. The main body remains closed, manifold and outward, about 3.062 m3.
  GLB reimport found 216 geometries and 157420 triangles; all 10 recorded output
  hashes matched, and the source scene was preserved.

The currently selected reconstruction is
`runs/countach-20261016/02-mesh-connections-v2/model.blend`, with sibling GLB and
millimetre OBJ. `connection-review/connection-comparison.png` compares actual
Blender renders against the original v3 scene. Reproduce the comparison with:

```powershell
python scripts/compare_blender_models.py `
  --before runs/countach-20261016/02-mesh-connections/baseline `
  --after runs/countach-20261016/02-mesh-connections-v2 `
  --output runs/countach-20261016/connection-review
```

`render-*.png` are inspection renders from the reconstructed smooth car. They
support silhouette/connection review and visual correction; they are neither
the original GPT image inputs nor final LEGO renders. Downstream conversion
consumes the exported mesh. This iteration has not produced or validated a new
Studio model. Lamp/intake detail and overall likeness still need refinement;
no delivery acceptance or main-branch merge is implied. The earlier full suite
passed 294 tests; after adding two seam-removal regressions, 27 focused model
quality/Blender tests passed.
