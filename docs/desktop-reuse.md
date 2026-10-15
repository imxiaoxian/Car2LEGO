# Desktop Frontend Reuse

The desktop interface is copied from `D:/lego/frontend`: Next.js pages, styles,
brand selection, original showcase assets, vehicle catalog, photo input, design
details, customization, references, parts and the Three.js assembly viewer.
The original workspace is read-only. No original backend server, database or
recovery loop is started. `scripts/frontend_bridge_worker.py` imports only the
required services in a subprocess with isolated storage and Numba cache paths.

`src/car2lego3d/desktop.py` implements the original frontend API contract over
this project's local task files. The generation workflow uses researched
dimensions, GPT reference images, four jointly conditioned Hunyuan3D-2mv views,
vehicle-family recipes, native checks and Studio export. An untextured mesh is
not used to infer paint: generated reference appearance supplies body color.
Customizations create a new job and pass the request through image generation.

Pause takes effect at a stage boundary; an in-flight model call can finish.
Resume reuses completed, hash-matching outputs. Regenerating an upstream stage
invalidates downstream stages. Retry preserves the prior draft and rebuilds
the assembly in a revision directory; it is currently an assembly-wide refit,
not an independent module solver. Unsupported scales or body recipes fail with
an explicit reason. Mechanism controls appear only when the exported scene
contains joints; current generated drafts do not claim working doors or steering.

## Verification, 2026-10-15

- Next.js production build passed.
- 150 Python tests passed, covering original routes and the new contract, optional year,
  image validation, same-origin restrictions, pause/resume/cancel, revision
  preservation, four-view routing and paint selection. Pipeline orchestration
  tests use mocked model outputs; they do not establish model quality.
- Playwright tests passed at 1440x1000 and 1920x1080: brand search, custom brand,
  photo upload/removal, catalog filtering, query prefill, old task links, real
  geometry loading, canvas pixel variation, orbit, wireframe, steps, modal,
  customization input and artifact downloads.
- Real Lotus candidate `46025e7747e24c4580ab82f99bb0425b` reuses the previously
  generated GPT views and reconstructed Hunyuan mesh. This frontend migration
  did not rerun those model stages. Its revised assembly has 321 parts,
  0 detected native collisions and 1 connected component. Export includes
  Studio, LDraw, MPD, CSV, XML, six rendered views and a 58-page draft PDF.
- Native dimensions are 222.4 x 88.0 x 67.2 mm. At 1:24, length is 4.60% over
  target; tyre checks also fail. Appearance, Studio GUI opening, insertion
  paths and physical assembly remain unverified. These results are a draft,
  not evidence that project delivery quality has been reached.

Run with `scripts/start-web.ps1` (frontend 8768, API 8767). The older UI at 8766
is left running for comparison. Browser tests: set `DESKTOP_JOB` to a real task
ID and run `npm run test:desktop` from `frontend`. `CHROME_PATH` can override the
local Chrome executable; `DESKTOP_URL` can override the frontend URL.

No user-provided acceptance image is embedded as a template, output target or
automatic acceptance rule. Official showcase photos remain source UI assets.
