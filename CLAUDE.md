# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Car2LEGO** — generates BrickLink Studio `.io` files for any car model. Input: car photo or text (make+model+year). Output: Studio `.io` file with parts list + reference pricing. User opens in BrickLink Studio 2.0 for 3D viewing, photorealistic rendering, building instructions, and parts export.

**Architecture**: Studio is the rendering engine. We generate `.io` files — Studio does everything visual.

## Quick Start

```bash
cd D:/lego/backend
pip install fastapi uvicorn sqlalchemy aiosqlite anthropic httpx celery redis alembic openai --quiet

# Start (SQLite dev — no PostgreSQL/Redis needed)
DATABASE_URL="sqlite+aiosqlite:///test.db" REDIS_URL="" GENERATION_MODE=sync \
  DEEPSEEK_API_KEY="sk-xxx" DOUBAO_API_KEY="ark-xxx" REBRICKABLE_API_KEY="xxx" \
  uvicorn app.main:app --port 8000

# Seed the LEGO car database (140 sets, requires REBRICKABLE_API_KEY for real parts)
DATABASE_URL="sqlite+aiosqlite:///test.db" REBRICKABLE_API_KEY="xxx" python ../data/seed_sets.py

# Run tests
cd D:/lego/backend
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite --quiet
python -m pytest tests/unit/ -v

# API docs: http://localhost:8000/docs
```

## Architecture

```
Input: Text (make+model+year) OR Car photo (Vision) OR 3D model (.obj/.stl)
    ↓
FastAPI backend (Python, SQLite/PostgreSQL)
    ├── Matching Engine: L1 (140 LEGO sets) → L2 (MOC) → L3 (templates) → L4 (AI)
    ├── Web Research: Google/official sites → structured car specs
    ├── AI Providers (multi-vendor):
    │   ├── DeepSeek (text → design generation, L4)
    │   ├── Doubao (vision → image analysis)
    │   └── Anthropic (legacy fallback)
    ├── Community Mod System: Steam Workshop-style mod sharing
    ├── Rebrickable API: real parts import for L1 matches
    └── Pricing Service: BrickLink reference prices
    ↓
Studio .io file (ZIP: model.ldr + model2.ldr + .info + thumbnail.png)
    ↓
Open in BrickLink Studio 2.0
    ├── 3D view + orbit/zoom
    ├── Photorealistic render (Eyesight GPU / POV-Ray CPU)
    ├── Auto-generate building instructions
    ├── Parts list → BrickLink XML export
    └── PartDesigner: custom decals/paint
```

## AI Provider Architecture

Multi-vendor LLM abstraction in `app/integrations/`:

```
app/integrations/
├── provider.py                     # LLMResponse, BaseLLMProvider, mask_api_key()
├── providers/
│   ├── __init__.py                 # Factory: create_text_provider(), create_vision_provider()
│   ├── anthropic.py                # AnthropicProvider (Claude SDK)
│   ├── openai.py                   # OpenAIProvider (DeepSeek + OpenAI, OpenAI SDK)
│   └── doubao.py                   # DoubaoProvider (Volcano Engine Responses API)
├── llm.py                          # LegoDesignClient (provider-agnostic)
└── ...
```

**Provider routing** (configurable via env vars):

| Config | Default | Purpose |
|--------|---------|---------|
| `AI_TEXT_PROVIDER` | `deepseek` | Text→design generation (L4) |
| `AI_VISION_PROVIDER` | `doubao` | Image→car features analysis |
| `DEEPSEEK_MODEL` | `deepseek-chat` | Model name for DeepSeek |
| `DOUBAO_VISION_MODEL` | `doubao-seed-2-1-pro-260628` | Model name for Doubao |

**How call sites use providers** — All 4 call sites now go through `LegoDesignClient.call_tools()` or `VisionAnalyzer._provider.create_message()`. Tool schemas remain in Anthropic format; `OpenAIProvider` and `DoubaoProvider` convert internally.

**Key security feature**: `mask_api_key()` in `provider.py` — all API keys are masked in error messages and log output. Real keys stored only in `_api_key` private attribute.

## Core Services

| Service | File | Purpose |
|---------|------|---------|
| Matching Engine | `matching_engine.py` | L1→L4 cascade: 140 sets → MOC → templates → AI. FLAGSHIP_SPECS for 9 Technic supersets (6 Ultimate + 3 F1) |
| Vision Analyzer | `vision_analyzer.py` | Car photo → 52 sub-styles, 80+ features via Doubao |
| Vehicle Taxonomy | `vehicle_taxonomy.py` | Complete classification system |
| Studio Designer | `studio_design_generator.py` | AI → LDraw → .io pipeline (DeepSeek primary, 1:38 only) |
| Studio Service | `studio_service.py` | .io ZIP read/write/merge (Studio 2.26.6 format) |
| Studio Templates | `studio_templates.py` | 6 car chassis templates (sports/SUV/sedan/pickup/hatch/F1) + SCALE_SPECS |
| Studio Automation | `studio_automation.py` | pywinauto → control Studio desktop app |
| Mod Catalog | `mod_parts_catalog.py` | 24 real-world mods × LEGO part mappings |
| Parts Knowledge | `lego_parts_knowledge.py` | 80-part curated catalog for AI |
| Community Mods | `community_mods.py` | Steam Workshop-style mod repository |
| Car Research | `car_research.py` | Web search → car specs (70+ brand domains) |
| Customization | `customization_service.py` | Apply mods to existing designs |
| Pricing | `pricing_service.py` | BrickLink reference prices per part |

## API Endpoints

```
POST /api/v1/designs              — Create design (text input, scale param: "1:38" default)
GET  /api/v1/designs/scales       — List supported scales + capabilities
POST /api/v1/designs/from-image   — Create design (image upload, Vision analysis)
GET  /api/v1/designs/{id}         — Design detail + parts + match info
GET  /api/v1/designs/{id}/status  — Poll async generation status
GET  /api/v1/designs/{id}/pricing — Reference pricing for parts
GET  /api/v1/designs/{id}/ldr     — Raw LDraw content
POST /api/v1/designs/{id}/customize — Customize existing design
POST /api/v1/designs/{id}/studio-open — Launch design in Studio

GET  /api/v1/templates            — 6 car body templates
GET  /api/v1/mods                 — 24 mod parts catalog
POST /api/v1/research             — Web research for unknown cars
GET  /api/v1/research/taxonomy-suggestions — New taxonomy entries

GET  /api/v1/community            — Browse community mods
POST /api/v1/community/submit     — Submit a community mod

GET  /api/v1/export/xml/{id}      — BrickLink Wanted List XML
GET  /api/v1/export/csv/{id}      — Parts CSV
GET  /api/v1/export/ldr/{id}      — LDraw .ldr file
GET  /api/v1/export/io/{id}       — Studio .io file

GET  /api/v1/sets/known-cars      — 140 known LEGO car sets
GET  /api/v1/cars/lookup          — Validate car via NHTSA API
```

## Environment Variables

```
# AI Providers (required)
DEEPSEEK_API_KEY=sk-...          # DeepSeek — text design generation (L4)
DOUBAO_API_KEY=ark-...           # Doubao — vision/image analysis

# AI Provider Config (optional, defaults shown)
AI_TEXT_PROVIDER=deepseek        # "deepseek" | "anthropic" | "openai"
AI_VISION_PROVIDER=doubao        # "doubao" | "openai" | "anthropic"
DEEPSEEK_MODEL=deepseek-chat     # Use deepseek-v4-pro for v4 (auto-strips tool_choice)
DOUBAO_VISION_MODEL=doubao-seed-2-1-pro-260628

# Legacy Anthropic (fallback only)
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=sqlite+aiosqlite:///test.db  # Dev default
REDIS_URL=                        # Empty = sync fallback (no Celery needed for dev)
GENERATION_MODE=sync              # "sync" | "async" | "auto"

# External APIs
REBRICKABLE_API_KEY=              # Required for L1 parts import
STUDIO_PATH=D:\lego\Studio 2.0\Studio.exe
```

## Scale System

Four supported scales. AI generation supports 1:38 only; other scales require matching an official LEGO set.

| Scale | AI Gen | Parts Source | Reference Sets |
|-------|--------|-------------|----------------|
| **1:38** | ✅ Yes | AI (20-40 parts, 200-350 total) | 76919(245) 76920(344) 77242(275) |
| **1:12** | ❌ No | Rebrickable import only | 10295(1458) 10337(1506) 10304(1456) |
| **1:10** | ❌ No | Rebrickable import only | 42154(1466) 42156(1775) 42171(1642) |
| **1:8** | ❌ No | Rebrickable import only | 42056(2704) 42083(3599) 42115(3696) 42143(3778) 42172(3893) 42232(4104) |

Scale profiles in `studio_templates.py` → `SCALE_SPECS`. AI prompt receives dimensions via `format_scale_for_prompt()`.

## Design Pipeline (Two Paths)

**Path A — Official Set Match (L1)**:
```
L1 match → Rebrickable API imports real parts → _build_io_from_parts() creates .io
```
Parts are real LEGO elements with correct colors/quantities. .io arranges them in a grid layout for browsing in Studio.

**Path B — AI Generation (L4, 1:38 only)**:
```
No match → classify_car_to_template() → AI customizes template → .io file
```
AI system prompt is Speed Champions 8-wide. Template registry has 6 body styles (sports/SUV/sedan/pickup/hatch/F1) with brand mappings.

**Path C — Unsupported**:
```
No match + scale ≠ 1:38 → returns error: "AI generation only supports 1:38"
```

Key implementation: `_build_io_from_parts()` in `designs.py` + `_import_set_parts()` for Rebrickable. Must `await db.flush()` after setting `file_io_path` to persist before `db.refresh()`.

## Flagship Specs

`matching_engine.py` → `FLAGSHIP_SPECS` dict maps 9 set numbers to mechanical specs:
- 6 Ultimate Car Concept (42056/42083/42115/42143/42172/42232): engine, transmission, door type, suspension, distinctive features, hp, body proportions
- 3 premium Technic (42156/42206/42207): Le Mans + F1 specs

L1 matches auto-enrich `MatchResult.metadata["flagship"]` → stored in `Design.metadata_` → passed to AI generator as `flagship_metadata` param.

## Web Research Pipeline

When a car is not in the database:
1. Build prioritized search queries (official site → Wikipedia → auto sites)
2. 70+ manufacturer domains mapped (byd.com, porsche.com, etc.)
3. Claude extracts specs from search results
4. Structured data feeds the design generator

## Community Mod System (MOD_SPEC v1.0)

```json
{
  "mod_id": "gt_wing_v2",
  "name": "GT Wing V2",
  "version": "1.0.0",
  "author": "username",
  "category": "aerodynamics",
  "difficulty": "medium",
  "estimated_parts": 12,
  "compatible_body_styles": ["sports_car", "coupe"],
  "ldraw_file": "model.ldr",
  "preview_image": "preview.png"
}
```

## Database Compatibility

Models use generic SQLAlchemy types (`JSON`, `Uuid`) — works with both PostgreSQL and SQLite.
**Use Alembic for schema changes**: `alembic revision --autogenerate -m "description"` then `alembic upgrade head`.
On first startup, `main.py` runs `alembic upgrade head` automatically (falls back to `create_all` if no migrations exist).
Seed data: 140 LEGO car sets across Speed Champions (88), Technic (32), Icons/Creator Expert (20).

## Testing

```bash
# Install test deps (one-time)
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite --quiet

# Unit tests (59 tests across 5 modules)
python -m pytest tests/unit/ -v

# With coverage
python -m pytest tests/unit/ -v --cov=app --cov-report=term-missing

# Integration tests
python -m pytest tests/integration/ -v
```

**Test structure**:
```
backend/tests/
├── conftest.py                              # Shared fixtures (async DB session, mock factories)
├── unit/services/
│   ├── test_matching_engine.py              # L1→L4 cascade (9 tests)
│   ├── test_pricing_service.py              # Part price estimation (13 tests)
│   ├── test_color_service.py                # RGB→LEGO color mapping (11 tests)
│   ├── test_ldraw_service.py                # LDraw format generation (11 tests)
│   └── test_vehicle_taxonomy.py             # Classification system (15 tests)
└── integration/
    └── test_api.py                          # End-to-end API tests
```

CI: `.github/workflows/ci.yml` — backend tests (Python 3.11/3.12) + frontend lint/build on push/PR.

## Key Files Quick Reference

```
backend/
├── alembic/                        # DB migrations (auto-generated, run on startup)
│   └── versions/001_initial.py     # Initial migration (8 tables)
├── tests/
│   ├── conftest.py                 # Shared fixtures (async DB, factories)
│   ├── unit/services/              # 59 unit tests across 5 files
│   └── integration/test_api.py     # API integration tests
├── app/
│   ├── main.py                     # App entry, CORS, auto-migrate (alembic + create_all fallback)
│   ├── config.py                   # Settings: DB, Redis, AI providers, API keys
│   ├── api/v1/
│   │   ├── designs.py              # Core API + _import_set_parts, _build_io_from_parts, _run_sync_generation
│   │   ├── research.py             # Web research + taxonomy suggestions
│   │   ├── community.py            # Mod repository CRUD
│   │   ├── mods.py                 # Built-in mod catalog
│   │   ├── templates.py            # Body style templates
│   │   ├── cars.py, sets.py, parts.py  # Supporting endpoints
│   │   └── export.py               # File export (XML/CSV/LDraw/.io)
│   ├── services/
│   │   ├── studio_design_generator.py  # AI → Studio .io pipeline (async, PRIMARY)
│   │   ├── design_generator.py         # DEPRECATED — use StudioDesignGenerator
│   │   ├── vision_analyzer.py          # Image→features via Doubao (async)
│   │   ├── vehicle_taxonomy.py         # 52 sub-styles, 80+ features, 47 colors
│   │   ├── studio_service.py           # .io read/write/merge
│   │   ├── studio_templates.py         # 5 car chassis LDraw templates
│   │   ├── studio_automation.py        # Windows UI automation for Studio
│   │   ├── customization_service.py    # Apply mods to designs
│   │   ├── community_mods.py           # Mod repository + MOD_SPEC
│   │   ├── mod_parts_catalog.py        # 24 real-world mods
│   │   ├── lego_parts_knowledge.py     # 80-part curated catalog
│   │   ├── car_research.py             # Web search → car specs
│   │   ├── pricing_service.py          # Reference pricing (estimated)
│   │   ├── matching_engine.py          # L1→L4 cascade
│   │   ├── color_service.py            # RGB→LEGO nearest color
│   │   ├── ldraw_service.py            # LDraw format helpers
│   │   └── export_service.py           # BrickLink XML/CSV generation
│   ├── integrations/
│   │   ├── provider.py                 # BaseLLMProvider, LLMResponse, mask_api_key()
│   │   ├── providers/
│   │   │   ├── __init__.py             # Factory: create_text/vision_provider()
│   │   │   ├── anthropic.py            # AnthropicProvider (Claude SDK)
│   │   │   ├── openai.py               # OpenAIProvider (DeepSeek + OpenAI)
│   │   │   └── doubao.py               # DoubaoProvider (Volcano Responses API)
│   │   ├── llm.py                      # LegoDesignClient (provider-agnostic)
│   │   ├── nhtsa.py                    # NHTSA car validation
│   │   └── rebrickable.py              # Rebrickable API (L1 parts import)
│   └── tasks/
│       ├── generation.py               # Celery: AI → .io
│       └── customization.py            # Celery: mod application
├── pytest.ini                          # Pytest config (asyncio auto, coverage)
└── requirements.txt                    # Python dependencies
```
