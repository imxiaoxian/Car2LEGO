# Native Windows and Lights

The glazing layout partitions the reconstructed cabin interval into panes,
pillars and a rear quarter. Dynamic programming penalizes unnecessary opaque
fillers and seams while keeping every pane inside its allotted interval.
Four-door cabins place their principal pillar earlier than two-door cabins.
Long cabins use a three-plate rear quarter panel under a native sloped surround;
short cabins retain full-height panes. A dark sill and header join the panes
visually. Native parts remain rigid, with no stretched glass geometry.

This layout is shared by the closed-cabin coupe and SUV builders. The existing
front/rear windscreen part families still limit the achievable rake and width.
The window layout is a constrained styling approximation, not recovered window
boundaries or vehicle CAD.

The sculpted SUV builder uses continuous two-stud white DRL tiles on dark plates
and clear rectangular lower lenses. The earlier glazing-v2 experiment used
paired rounded clear lenses and round lower projectors instead.
Separate side-mounted projectors are added only for the Lotus For Me styling
prior or a reference brief identifying split lamps. The rear light bar uses
four- and two-stud red tiles viewed along their one-plate edge, supported by a
dark belt. This avoids presenting side-stud sockets through a broad lens face.

The presentation bridge loads the Studio colour table in its own process.
The original renderer's small default palette treated smoke glass and red
lenses as grey. The browser viewer now includes smoke glass and the supported
body colours, with lower glass roughness and separate clear/smoke/lens opacity.
These are preview materials; the Studio export retains native LDraw colours.

## Lotus For Me Comparison

The local comparison reuses the images, calibrated mesh, specifications and
1:24 scale of job `d3daf39dfe9344a88c7482a09573fc9b`. No image/model API calls
were needed. Outputs are in `runs/glazing-v2-lotus`; the independently published
draft is `27a6ef85936b4c0a967d083fa6845312`.

The revised draft has 332 native parts, zero detected collisions and verified
Studio archive roundtrip. Both the baseline and revised assembly have two
disconnected body parts; no new glazing/light part is disconnected. Studio GUI
opening and physical assembly remain unverified. These results do not establish
overall appearance acceptance or dimensional accuracy.

The before/after presentation renders use the same corrected colour table so
geometry changes can be inspected separately from the colour correction.

Validation: 79 focused Python tests passed. The full suite had 234 passes and
one Windows connection reset while an HTTP-origin test read a rejection; that
test passed when rerun alone. The production frontend build passed. Playwright
checks at 1440x1000 and 1920x1080 passed with nonblank canvas pixels, actual
green body pixels, rotation interaction and no browser runtime errors.
