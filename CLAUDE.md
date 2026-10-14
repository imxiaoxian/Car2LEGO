# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Car2LEGO** — generates BrickLink Studio `.io` / LDraw files for a car model. Input: car photo or text (make+model+year). Output: assembled model + parts list + reference pricing, viewable in an in-repo Three.js viewer or opened in BrickLink Studio 2.0.

**Architecture**: the backend builds a real, connection-validated LEGO scene; Studio (or the Three.js viewer) does the rendering.

## Quick Start

```bash
cd D:/lego/backend
pip install -r requirements.txt --quiet

# Start (SQLite dev needs no PostgreSQL/Redis; Postgres via docker-compose)
DATABASE_URL="sqlite+aiosqlite:///test.db" REDIS_URL="" \
  OPENAI_API_KEY="..." DESIGN_WORKFLOW=assembly_v3 \
  uvicorn app.main:app --port 8000

# Seed reference data (both require a DB; run from repo root)
DATABASE_URL="sqlite+aiosqlite:///test.db" python data/seed_sets.py          # 140 LEGO car sets
DATABASE_URL="sqlite+aiosqlite:///test.db" python data/seed_car_specs.py     # 50 car spec rows

# Run tests (285 collected by default; slow/real-API tests deselected)
cd D:/lego/backend
python -m pytest tests/ -v

# API docs: http://localhost:8000/docs   |   Frontend: cd D:/lego/frontend && npm run dev
```

## Architecture

```
Input: Text (make+model+year) OR Car photo OR 3D model
    ↓
FastAPI backend (Python, SQLite/PostgreSQL)
    ├── Matching Engine: L1 (140 LEGO sets) → L2 (MOC) → L3 (templates) → L4 (AI)
    ├── Web Research: manufacturer/Wikipedia/auto sites → car specs
    ├── Design generation: DESIGN_WORKFLOW → assembly_v3 (default) | v2 | legacy
    ├── Single OpenAI-compatible gateway for all text + vision (see AI below)
    ├── Vision Analyzer: car photo → taxonomy features
    ├── Rebrickable API: real parts import for L1 matches
    └── Pricing Service: BrickLink reference prices
    ↓
AssemblyScene (validated parts + connections + joints + build steps)
    ├── Studio .io / MPD / LDR / PDF export  → open in BrickLink Studio 2.0
    └── scene.json / geometry endpoint       → Three.js viewer (AssemblyViewer.tsx)
```

## Design Generation (PRIMARY: assembly_v3)

`assembly_v3` is an evidence-based, recipe-driven generator. It solves a discrete stud
grid with OR-Tools CP-SAT, builds a physical assembly, and validates real connections
against Studio's own connectivity/collider files before export.

```
app/services/assembly_v3/            # the generator package
├── pipeline.py       # AssemblyPipeline.generate(): resumable orchestration, checkpoints, repair loop
├── recipes.py        # solve_grid() (CP-SAT) + build_f40() router → f40.py or f40_detail.py
├── f40.py            # stud-lattice F40 shell, recipe "f40-shell-3"
├── f40_detail.py     # 1:24 native slope/mudguard surface, recipe "f40-surface-4"
├── specifications.py # SCALES, CAPABILITIES, F40_SPEC, target_dimensions()
├── validation.py     # digital gates: collisions(), move_joint(), motion_report(), validate_scene()
├── connections.py    # infers connections from Studio .conn world ports
├── catalog.py        # reads .conn port data, port()/part_validity()
├── scene.py          # AssemblyScene / PartInstance / Module / Joint / BuildStep (Pydantic)
├── repair.py         # score() + repair_module()
├── jobs.py           # JobStore: lease/checkpoint/recover, call budgets
├── exports.py        # Studio .io, MPD, flat LDR, inventory, PDF
├── render.py         # CPU raster scene renders
└── official_guides.py# official instruction guides from storage

# scene.planning["recipe"] records the recipe used ("f40-shell-3", "f40-surface-4",
# "experimental-coupe-scaffold" for non-F40 vehicles built from estimated dimensions)
```

- **Scales** (`specifications.py` → `SCALES`): `1:38`, `1:24`, `1:16`, `1:12`. 1:10 / 1:8 are NOT
  supported by this generator. `CAPABILITIES` maps each scale to its mechanisms
  (rolling_wheels → doors, steering, independent_suspension).
- **Scale requirements** (`requirements.py`, `scale_requirements_v1`): the single source
  for appearance, mechanism instance counts, reference views, required/recommended
  measurements, tolerances and step limits. New jobs/scenes snapshot the policy;
  resume uses that snapshot. Old reports are not upgraded. See `docs/scale-requirements.md`.
- **Routing** — `DESIGN_WORKFLOW` (default `assembly_v3`) is read in:
  - `app/config.py:74` (default)
  - `app/services/studio_design_generator.py:145/150/199` — assembly_v3 → `AssemblyPipeline.generate()`, else `legacy` → `design_graph_legacy`, else → v2 `design_graph`
  - `app/api/v1/designs.py:226/658/1004/1145` — job dispatch + customize paths
  - `app/main.py:57` — startup recovery loop re-drives `assembly_v3` jobs

## Services & Modules

| Area | File | Purpose |
|------|------|---------|
| Matching | `services/matching_engine.py` | L1→L4 cascade; `FLAGSHIP_SPECS` for 9 Technic supersets |
| Assembly gen | `services/assembly_v3/` | Primary generator (see above) |
| Geometry | `services/assembly_geometry.py` | Reads Studio collider `*.col` boxes → world AABBs |
| Preview render | `services/assembly_preview.py` | `geometry_bounds()`, `render_preview()` (CPU), `part_triangles()` |
| IO validator | `services/io_validator.py` | Validates `.io`; resolves Studio ldraw paths (`STUDIO_LDRAW_PARTS`) |
| Studio service | `services/studio_service.py` | `.io` ZIP read/write/merge |
| Templates | `services/studio_templates.py` | 6 chassis templates + `SCALE_SPECS` |
| Studio automation | `services/studio_automation.py` | pywinauto → drive Studio desktop app |
| Section planner | `services/section_planner.py` (+ `section_evaluator`, `section_inspector`) | v2 section workflow |
| Vision analyzer | `services/vision_analyzer.py` | Car photo → features |
| Vehicle taxonomy | `services/vehicle_taxonomy.py` | Classification system |
| Reference images | `services/reference_images.py` | gpt-image reference shots + progress |
| Brand features | `services/brand_features.py` | Brand design cues |
| Car research | `services/car_research.py` | Web search → car specs (brand domains) |
| Car specs | `services/car_specs_service.py` | `car_specs` knowledge base lookups |
| Customization | `services/customization_service.py` | Apply mods to designs |
| Community mods | `services/community_mods.py` | Mod repository + MOD_SPEC |
| Mod catalog | `services/mod_parts_catalog.py` | Real-world mods × LEGO mappings |
| Parts knowledge | `services/lego_parts_knowledge.py` | Curated part catalog |
| Pricing | `services/pricing_service.py` | BrickLink reference prices |
| Export | `services/export_service.py` | BrickLink XML/CSV |
| Color | `services/color_service.py` | RGB → nearest LEGO color |

**AI layer** — all text and vision go through one OpenAI-compatible gateway:
`app/agents/models.py` → `create_text_llm()` / `create_vision_llm()`, backed by
`GatewayChatOpenAI` (validates JSON locally; the gateway rejects tool calls, so structured
output is done by prompt + `PydanticOutputParser`). Config: `OPENAI_API_KEY`, `OPENAI_BASE_URL`,
`OPENAI_MODEL`, `OPENAI_IMAGE_MODEL`, `TEXT_MAX_TOKENS`, `VISION_MAX_TOKENS`. The legacy
`app/integrations/providers/` package no longer exists — `app/integrations/` holds only
`base.py`, `nhtsa.py`, `rebrickable.py`.

**Agent graphs** (`app/agents/`): `design_graph.py` (v2 section workflow), `design_graph_legacy.py`,
`section_graph.py`, `vision_graph.py`, `customization_graph.py`, `state.py`, `models.py`, `tools.py`.

## Studio Integration

`settings.studio_ldraw_path` (env `STUDIO_LDRAW_PATH`, default `D:/lego/Studio 2.0/ldraw`) points
at the user's local Studio install. The generator reads, under that path:
- `connectivity/<part>.conn` — connectivity ports (`assembly_v3/catalog.py`)
- `collider/<part>.col` — oriented collision boxes (`services/assembly_geometry.py`)
- `parts/`, `parts/s/`, `p/`, `UnOfficial/parts/` — LDraw geometry (`services/io_validator.py`)

## API Endpoints

All under `/api/v1` (see `app/api/v1/router.py`). Derived from router decorators:

```
designs:  GET  /designs/scales
          POST /designs                         (text input)
          GET  /designs                         (list)
          GET  /designs/{id}  |  /{id}/status
          GET  /designs/{id}/reference-images/{view}
          GET  /designs/{id}/scene | /quality | /geometry
          GET  /designs/{id}/renders/{view}
          POST /designs/{id}/control/{action}
          GET  /designs/{id}/assembly-preview
          GET  /designs/{id}/ldr  |  /{id}/parts
          GET  /designs/{id}/open-in-studio
          POST /designs/from-image              (image upload)
          GET  /designs/{id}/pricing
          POST /designs/{id}/studio-open  |  /{id}/customize
cars:     GET  /cars  |  /cars/{car_id} ;  POST /cars/lookup
sets:     GET  /sets/vehicles | /sets | /sets/known-cars | /sets/{set_num}
parts:    GET  /parts
export:   GET  /export/mpd/{id} | /xml/{id} | /csv/{id} | /ldr/{id} | /io/{id} | /pdf/{id}
mods:     GET  /mods  |  /mods/categories
templates:GET  /templates
community:GET  /community | /categories | /spec | /{mod_id} | /{mod_id}/ldr ; POST /community/submit
research: POST /research  (returns search queries + suggested sources; no live fetch)
          GET  /research/taxonomy-suggestions ; POST /research/taxonomy-suggestions/clear
```

## Environment Variables

Names only (defaults from `app/config.py`). Never commit real key values.

```
DATABASE_URL=…            DATABASE_URL_SYNC=…      REDIS_URL=…
STORAGE_PATH=./storage    STUDIO_LDRAW_PATH=D:/lego/Studio 2.0/ldraw
OPENAI_API_KEY=  OPENAI_BASE_URL=  OPENAI_MODEL=gpt-6.1-sol  OPENAI_IMAGE_MODEL=
IMAGE_QUALITY=  IMAGE_SIZE=  IMAGE_TIMEOUT=
TEXT_MAX_TOKENS=32768     VISION_MAX_TOKENS=8192
DESIGN_WORKFLOW=assembly_v3
ASSEMBLY_TEXT_CALL_LIMIT=64  ASSEMBLY_IMAGE_CALL_LIMIT=12  ASSEMBLY_MODULE_REPAIR_LIMIT=3
ASSEMBLY_REPLAN_LIMIT=2       ASSEMBLY_LEASE_SECONDS=900
REBRICKABLE_API_KEY=  BRICKLINK_API_KEY=  BRICKLINK_API_SECRET=
GENERATION_MODE=sync|async|auto    (read via os.getenv in designs.py; sync = inline, no Celery)
DEBUG=  CORS_ORIGINS=
# Legacy/retained (unused by the gateway path): ANTHROPIC_*, DEEPSEEK_*, DOUBAO_*
```

## Data & Database

- **Models** (`app/models/`, 8 files): `car`, `car_spec`, `design` (Design + DesignPart), `lego_set`,
  `moc`, `part` (Part + PartColor), `template` (DesignTemplate), `user`.
- **Tables** (10): `cars`, `car_specs`, `designs`, `design_parts`, `lego_sets`, `mocs`, `parts`,
  `part_colors`, `design_templates`, `users`. Generic SQLAlchemy types (`JSON`, `Uuid`) → works on
  SQLite and PostgreSQL.
- **Alembic** (`backend/alembic/versions/`): `001_initial.py` (9 tables), `002_car_specs.py` (car_specs).
  `main.py` runs `alembic upgrade head` on startup, falling back to `create_all`.
- **Seeds** (`data/`): `seed_sets.py` → 140 rows (Speed Champions, Technic, Creator Expert/Icons, …);
  `seed_car_specs.py` → 50 rows across major makes (Ferrari, Porsche, McLaren, Lamborghini, …).

## Scale System

`SCALE_SPECS` in `services/studio_templates.py` and `SCALES`/`CAPABILITIES` in
`services/assembly_v3/specifications.py`. assembly_v3 supports `1:38`, `1:24`, `1:16`, `1:12`
(experimental — digital/Studio/physical acceptance required; F40 recipes exist per scale).
The v2/legacy image-guided path supports `1:38` only.

## Testing

```bash
cd D:/lego/backend
python -m pytest tests/ -v                       # 285 collected (slow tests deselected)
python -m pytest tests/unit/ -v --cov=app        # fail_under = 60 (pytest.ini)
python -m pytest tests/integration/ -v
```

`pytest.ini`: `testpaths = tests`, `asyncio_mode = auto`, `addopts = -v --tb=short --color=yes -m "not slow"`,
markers `slow` / `integration` / `unit`. Test tree (31 files):

```
tests/
├── conftest.py
├── unit/agents/     8 files (design_graph, section_graph, vision_graph, tools, …)
├── unit/services/  17 files (assembly_v3, assembly_geometry, matching_engine, pricing, …)
├── unit/{models,integrations}/  __init__.py only
└── integration/     6 files (test_api, test_api_e2e, test_assembly_v3_api, …)
```

## CI / Docker / Celery

- **CI** (`.github/workflows/ci.yml`): `backend-tests` (Python 3.11/3.12 — ruff `E,F,W` lint,
  `pytest tests/unit/`, then `test_api_e2e.py test_api.py`, coverage → Codecov) and
  `frontend-tests` (Node 20 — `next lint`, `tsc --noEmit`, `next build`).
- **Docker**: `backend/Dockerfile` (python:3.12-slim, uvicorn), `frontend/Dockerfile` (node:20-alpine).
  `docker-compose.yml` services: `db` (postgres:16), `redis` (redis:7), `backend`, `celery-worker`
  (`celery -A tasks.celery_app`), `frontend`.
- **Celery** lives at `backend/tasks/` (package `tasks`, not `app.tasks`): `celery_app.py`,
  `generation.py`, `customization.py`, plus F40 dev/analysis scripts. With `GENERATION_MODE=sync`
  (or no `REDIS_URL`) generation runs inline — Celery is not required for dev.
- **Lint/format**: no `pyproject.toml`, ruff config file, or `.pre-commit-config.yaml` in the repo.
  Ruff is installed ad-hoc in CI; frontend uses `.eslintrc.json` + `tailwind.config.ts`.

## Security

API keys are masked in errors/logs by `mask_api_key()` in **`app/agents/security.py`**
(migrated out of the removed `app/integrations/provider.py`).

## Frontend

Next.js `^14.2.15` (App Router). Pages: `app/page.tsx`, `app/designs/[id]/page.tsx`, `app/sets/page.tsx`
(+ `layout.tsx`). Components: `components/viewer/AssemblyViewer.tsx` (Three.js scene viewer, loaded via
`next/dynamic` with `ssr:false`), `components/ProductImage.tsx`, `components/SiteHeader.tsx`.
API base URL in `lib/api.ts`: `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"`.

## Key Files Quick Reference

```
backend/
├── app/
│   ├── main.py               # App entry, CORS/GZip, alembic upgrade, assembly_v3 recovery loop
│   ├── config.py             # Settings (DB, storage, gateway model, DESIGN_WORKFLOW, budgets)
│   ├── api/v1/router.py      # Aggregates 9 routers under /api/v1
│   ├── api/v1/designs.py     # Core API + generate/dispatch/customize + _import_set_parts/_build_io_from_parts
│   ├── agents/               # LangGraph graphs (design v2, legacy, section, vision, customization) + models.py + security.py
│   ├── services/assembly_v3/ # PRIMARY generator package (pipeline, recipes, f40, validation, …)
│   ├── services/             # matching_engine, studio_*, vision_analyzer, geometry/preview, … (see table)
│   └── models/               # 8 model files / 10 tables
├── alembic/versions/         # 001_initial.py, 002_car_specs.py
├── tasks/                    # Celery app + task modules
├── tests/                    # 31 files, 285 collected
└── pytest.ini                # asyncio auto, -m "not slow", coverage fail_under 60
data/                         # seed_sets.py (140), seed_car_specs.py (50)
frontend/                     # Next.js 14 App Router + Three.js AssemblyViewer
```
