# Mesh-conditioned coupe fitting

The 2026-10-14 BMW M4 experiment exposes a layout error in the original car strategy:
its source roof interval was 11..19 studs, but the recipe collapsed it to 15..16.
Every car also received an integrated low canopy, rear engine cover, side intakes,
round tail lamps and a large wing. This erased the M4's silhouette even with correct
overall mesh dimensions.

## Changes

- Select a front-engine coupe layout for a resolved BMW M4 G82, or a sufficiently
  tall sourced car with a broad, distinct mesh roof. Low sports cars retain their
  existing recipe. Classification is a prior, not trained part segmentation.
- Extract the connected interval around the mesh's highest roof station. Keep its
  extent rather than forcing two studs. The stricter high-roof threshold excludes
  the windshield/rear-window shoulders; native glazing is placed separately.
- Quantize sourced height in 3.2 mm plates. Reserve windscreen cavities, attach a
  roof plate above the native glass, and give front and rear seats an interior void.
- Select compatible native tyre/rim families by a weighted diameter/width error.
  Quantize sourced wheel track separately from rectangular core width. The six-stud
  arches reserve tyre clearance and provide explicit mounting feet and stud finishes.
- Use an opaque bonnet and trunk, raked C pillars, tinted glazing, slim lamps,
  door skins and a small trunk lip. The G82's tall twin grille is explicitly tagged
  `styling_prior=bmw-m4-g82`; it is not claimed to have been recovered from the mesh.
- When a native renderer is configured, the shared CLI/web pipeline renders actual
  parts before packaging `.io`, embeds the preview, and shows it in the webpage.
  A configured render failure fails the run. An unconfigured renderer is recorded
  as unavailable and the webpage labels its mesh fallback accordingly.

## Controlled Comparison

`examples/bmw-m4-coupe-1-24/comparison-before` and `comparison-after` contain the
same original calibrated M4 mesh, spec snapshot, color, scale and axle constraints.
The conversion algorithm is the changed variable. Exact image/model hashes and
nominal dimensions are retained in `controlled-comparison.json`.

| Quantity | Previous recipe | Coupe recipe |
| --- | --- | --- |
| Fitted high-roof interval | 15..16 | 12..16 |
| Native glass | integrated low canopy | separate front/rear windscreens |
| Engine/trunk treatment | transparent rear engine cover | front bonnet, opaque trunk |
| Tyre diameter | 24 mm | 30.4 mm |
| Front tyre diameter error | -14.94% | +7.74% |
| Rear tyre diameter error | -15.55% | +6.96% |
| Nominal front/rear track | 72 / 72 mm | 68 / 68 mm |
| Nominal height | not reported | 57.6 mm, -0.76% |

These are nominal core/part-family measurements, not independently verified
native exterior dimensions. Tyre widths are still +22.18%/+17.89% above their
scale targets; overhang errors also remain. No tolerance was relaxed to pass them.

![Controlled conversion and complete new run](../examples/bmw-m4-coupe-1-24/comparison.png)

## Complete New Run

The published example also contains a new actual SD-Turbo -> rembg -> TripoSR ->
calibration -> coupe fit -> native Blender render -> Studio run:

```powershell
.venv/Scripts/python.exe -m car2lego3d run `
  --prompt "a blue 2023 BMW M4 G82 coupe" --seed 42 --steps 4 --resolution 256 `
  --vehicle-specs examples/bmw-m4-coupe-1-24/00-vehicle/spec.json `
  --scale 1:24 --color 1 --output runs/m4-reproduction
```

Configure the optional renderer as documented in README before this command to
include native preview. The measured pipeline duration was 88.199 seconds on the
existing RTX 4060 Laptop environment. Reconstruction produced 46,418 vertices and
92,820 faces; the mesh is watertight. The final LEGO draft has 328 parts and 36
steps. The renderer resolved every referenced part. `.io` archive readback retained
all part transforms, colors and steps; its thumbnail is the actual native preview.

The M4 specifications are the previous live research result from Auto-Data,
recovered after that skill run timed out. They are `reported`, not manufacturer
measurements. This experiment reuses that source snapshot; it does not claim a
fresh successful web search. Year remains optional in the application; 2023 is
only this experiment's image prompt within the resolved G82 source scope.

## Remaining Quality Gaps

The native renders were inspected. The coupe silhouette is improved, but the
body/roof still look too rectangular and the grille/light approximation is coarse.
SD-Turbo continued to generate an F82-like front even after G82-specific prompting
and several seed trials. The output must not be described as an accurate G82
reconstruction. Its styling prior corrects layout, not the underlying source image.

Door/window dimensions remain unknown; neither mesh fitting nor the part recipe
converts them into sourced measurements. Native collisions, clutch connectivity,
Studio GUI opening, moving mechanisms and physical construction remain unverified.
`appearance_accepted`, `physical_verified` and `delivery_accepted` remain false.
The user's detailed F40 reference is still the acceptance target, not a passed gate.
