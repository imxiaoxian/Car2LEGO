# Modular Vehicle Exterior

The SUV/crossover builder now fits a separate native-part shell over its support
grid. Chassis bricks are not used as the primary visible bonnet, roof or door
surface. This remains a constrained standard-parts approximation of a car.

## Fitting

- A symmetric two-dimensional strip planner chooses native tiles, bows and a
  six-stud-wide curved bonnet module. Its objective combines silhouette error,
  endpoint discontinuities, seams and small visible fillers. The per-station
  height error is bounded to one plate.
- Parts retain their native shape and rigid rotation. A 2x4 bow is a real 88930,
  not a stretched 15068. The 52031 bonnet uses its native offset origin, socket
  clearance and a separate tile over its top studs.
- Roof shoulders use four-stud-wide bows; the center uses larger tiles. Rear
  roof target heights descend according to the sampled mesh profile. Native
  curved pieces quantize that target; they do not recover exact vehicle CAD.
- Windshield sill estimates and mesh upper-body width jointly select a native
  six- or eight-stud part. A narrow roof cross section no longer determines the
  entire cabin width by itself. The estimates are not manufacturer measurements.
- Wheel wells, axle shafts, side studs, glass returns and shell sockets reserve
  space before the internal cells are packed. A layered floor beam connects the
  rear floor and seats to the chassis. Long SNOT door tiles and rear fascia tiles
  cover the exterior walls.

## Reproduce And Compare

Generate with the usual `car2lego3d lego --strategy car` command, then use
`scripts/native_audit_worker.py` and `scripts/frontend_bridge_worker.py render`
to check and render real Studio library geometry. Run:

```powershell
python scripts/compare_exterior.py --baseline runs/glazing-v2-lotus --candidate runs/modular-v7-lotus
```

The comparison records source hashes, module counts, collisions and disconnected
parts, and writes a two-view before/after image. Counts are not a likeness score.
The Lotus iteration reuses existing GPT images, dimensions and Blender mesh; it
does not claim a new image-generation or reconstruction run.

The model remains a review draft. Native collision/connectivity checks and IO
archive roundtrips do not verify Studio GUI behavior, clutch strength, assembly
order or a physical build. Lotus-specific fascia, body curvature and glazing
still require visual review; no automatic delivery acceptance is asserted.
