<div align="center">

<img src="https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python" alt="Python">
<img src="https://img.shields.io/badge/FastAPI-0.111+-teal?style=flat-square&logo=fastapi" alt="FastAPI">
<img src="https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=nextdotjs" alt="Next.js">
<img src="https://img.shields.io/badge/LangGraph-0.1+-orange?style=flat-square" alt="LangGraph">
<img src="https://img.shields.io/badge/Celery-async-green?style=flat-square&logo=celery" alt="Celery">
<img src="https://img.shields.io/badge/PostgreSQL-16-blue?style=flat-square&logo=postgresql" alt="PostgreSQL">
<img src="https://img.shields.io/badge/Redis-7-red?style=flat-square&logo=redis" alt="Redis">
<img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">

<h1>🚗 Car2LEGO</h1>
<h3>Turn Any Car into LEGO® Building Instructions</h3>

<p>
  <strong>AI-Powered LEGO Model Generation Platform</strong><br>
  LangGraph Agent · OpenAI Multimodal Models · Image References · Studio .io Output
</p>

</div>

---

## 📖 Overview

**Car2LEGO** is an experimental vehicle-to-LEGO assembly workspace. Enter a car make, model and year, or upload a photo, to generate inspectable **BrickLink Studio `.io` drafts**, parts lists and step documents. Physical buildability and precision appearance require separate acceptance.

### Scale-aware assembly generation

The default `assembly_v3` workflow uses `gpt-6.1-sol` for recognition and visual
planning, and `gpt-image-2.5-sunburst` for vehicle references. Native parts, connector
graphs, collision geometry and OR-Tools layout solving produce the assembly scene.
Every supported scale has its own appearance, mechanism, reference and measurement
requirements. Requirements are snapshotted for pause/resume and exposed in the UI.

After vehicle identification, the `research-vehicle-specifications` skill executes
web searches and reads manufacturer pages, automotive references and technical
PDFs. Dimensions, tyre sizes and available component geometry become inputs to
reference generation and assembly planning. Missing details trigger focused
follow-up searches; each measurement retains its original document and evidence.
See [vehicle research](docs/vehicle-physical-specifications.md).
Model year is optional for text and photo requests. Research begins after design
submission; each make/model/optional-year identity has its own cache. Completed
research can be reused, and the detail page search action refreshes it explicitly.

| Scale | Target | Required mechanisms | Default reference sheets |
| --- | --- | --- | --- |
| 1:38 | Recognizable compact exterior | Four rolling wheels | 6 |
| 1:24 | Full body, simplified cockpit and engine bay | Wheels, front hood, engine cover | 14 |
| 1:16 | Detailed cockpit, engine and door panels | Above plus both doors and steering | 18 |
| 1:12 | Layered body, detailed engine, interior and underbody | Above plus four independent suspension units | 20 |

These are acceptance targets. Outputs remain experimental drafts until independent
appearance, digital, Studio and physical checks pass. Opening covers, steering and
suspension do not yet have accepted recipes. See [scale requirements](docs/scale-requirements.md)
and [implementation and acceptance status](docs/assembly_v3-status.md).

Set `STUDIO_LDRAW_PATH` to a local Studio `ldraw` directory containing `parts`, `p`
and `collider` directories. The local default is `Studio 2.0/ldraw` under this repo.
Generation fails clearly if required geometry is missing.

Configure `backend/.env` for local development or root `.env` for Docker:

```dotenv
OPENAI_API_KEY=your_gateway_key
OPENAI_BASE_URL=https://api.lundong.ai
OPENAI_MODEL=gpt-6.1-sol
OPENAI_IMAGE_MODEL=gpt-image-2.5-sunburst
IMAGE_QUALITY=high
IMAGE_SIZE=1536x1024
IMAGE_TIMEOUT=300
DESIGN_WORKFLOW=assembly_v3
```

The gateway origin is normalized to `/v1`. It must support multimodal chat and
image generation/editing for these model IDs. Structured text uses local schema
validation. Image calls have no budget cap; additional detail sheets can be requested
as needed. Text calls default to a limit of 64. Cached references are reused when
restarting the same design with unchanged inputs.

With Redis, generation runs in Celery. Without Redis, the default `auto` mode
returns a pending design and runs generation in a local background task; keep
the backend running until completion. `GENERATION_MODE=sync` waits for completion.
The detail page polls progress and displays references as they become available.
Assembly generation supports `1:38`, `1:24`, `1:16` and `1:12`. `1:8` and `1:10`
remain closed. Official inventories supply reference stock information and do not
count as an assembled vehicle. Other vehicles remain experimental; F40 is the first
specialized recipe under development.

> 🧱 **What makes this special**: Not just another AI wrapper — a 4-level matching cascade from official LEGO sets to AI-generated custom designs, with a Steam Workshop-style community mod system.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    Next.js 14 Frontend                            │
│  Car Input · 3D Preview · Parts List · Community · Export        │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTP REST + WebSocket
┌───────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend                                │
│                                                                    │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐     │
│  │  Matching Engine │  │  LangGraph   │  │  Community Mods  │     │
│  │  L1→L4 Cascade  │  │  Agent (3)   │  │  (MOD_SPEC v1.0) │     │
│  └────────────────┘  └──────────────┘  └──────────────────┘     │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐     │
│  │  Vision Analyzer│  │  Car Research │  │  Export Service   │     │
│  │  (OpenAI)       │  │  (Specs)      │  │  (XML/CSV/LDraw)  │     │
│  └────────────────┘  └──────────────┘  └──────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────┐
│PostgreSQL│  │  Redis   │  │  Celery Worker│  │  AI Providers │
│          │  │ (Broker) │  │  (Async Gen)  │  │  (OpenAI)      │
└──────────┘  └──────────┘  └──────────────┘  └───────────────┘
                                                     │
                                    ┌────────────────┼────────────────┐
                                    ▼                ▼                ▼
                                gpt-6.1-sol       gpt-6.1-sol      gpt-image-2.5-sunburst
                                (Text/Design)     (Vision)        (References)
```

---

## ✨ Key Features

### 🎯 4-Level Matching Strategy

| Level | Strategy | Confidence | Example |
|-------|----------|------------|---------|
| **L1** | Exact LEGO set match (Speed Champions) | 95-100% | Porsche 911 → Set 76920 |
| **L2** | Community MOC match | 80-95% | User-submitted designs |
| **L3** | Category template adaptation | 50-80% | Sports car → chassis template |
| **L4** | AI voxel-based generation | 10-50% | Custom design from scratch |

### 🧠 LangGraph Agent Orchestration

Three specialized agent graphs:
- **Design Graph**: Orchestrates the full `text → .io` generation pipeline
- **Vision Graph**: `car photo → feature extraction → design parameters`
- **Customization Graph**: `existing design + mod → customized .io`

### 🤖 OpenAI Models

| Provider | Role | Model |
|----------|------|-------|
| **OpenAI-compatible gateway** | Recognition, planning, design, review, customization | gpt-6.1-sol |
| **OpenAI-compatible Images API** | Complete vehicle and component references | gpt-image-2.5-sunburst |

> 🔒 **Security-first**: All API keys are masked in logs via `mask_api_key()` — real keys stored only in private `_api_key` attributes.

### 📐 Scale System

| Scale | Generation | Precision acceptance |
| --- | --- | --- |
| **1:38** | Experimental native assembly | Independent checks required |
| **1:24** | Experimental native assembly | Independent checks required |
| **1:16** | Experimental native assembly | Independent checks required |
| **1:12** | Experimental native assembly | Independent checks required |
| **1:10 / 1:8** | Reserved, creation closed | No accepted recipe |

### 🏪 Community Mod System
- **MOD_SPEC v1.0** format with versioning
- 24 built-in real-world mods (GT wings, widebody kits, etc.)
- 80-part curated LEGO parts knowledge catalog
- Steam Workshop-style submission/browse functionality

### 🔍 Vehicle References
- Photo recognition preserves the identified year, paint and visible details
- Scale-specific generated exterior and detail sheets replace manufacturer photo searches
- Specification lookup remains available independently of image generation

---

## 🛠️ Tech Stack

### Backend
| Component | Technology | Details |
|-----------|-----------|---------|
| **Framework** | FastAPI + uvicorn | Async Python, auto-docs at /docs |
| **Agent** | LangGraph | 3 agent graphs with structured state |
| **Async Tasks** | Celery + Redis | AI generation in background workers |
| **Database** | PostgreSQL 16 + SQLAlchemy | Async with SQLite fallback for dev |
| **Cache/Broker** | Redis 7 | Celery broker + result backend |
| **LLM** | gpt-6.1-sol + gpt-image-2.5-sunburst | OpenAI-compatible gateway |
| **LEGO Format** | LDraw (.ldr) + Studio (.io) | ZIP-based format with parts + metadata |
| **Testing** | pytest-asyncio | 59 unit tests + integration tests |

### Frontend
| Component | Technology |
|-----------|-----------|
| **Framework** | Next.js 14 (App Router) |
| **UI** | React + TypeScript + Tailwind CSS |
| **3D Preview** | Three.js (planned) |
| **State** | React hooks + SWR |

### DevOps
| Component | Technology |
|-----------|-----------|
| **Infrastructure** | Docker Compose (4 services) |
| **CI/CD** | GitHub Actions (backend tests + frontend lint) |
| **Migrations** | Alembic (auto-run on startup) |
| **Desktop** | pywinauto → BrickLink Studio automation |

---

## 📦 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- Gateway API key with access to gpt-6.1-sol and gpt-image-2.5-sunburst

### Installation

```bash
# 1. Clone
git clone https://github.com/imxiaoxian/Car2LEGO.git
cd Car2LEGO

# 2. Configure
cp .env.example .env
# Edit .env with your API keys:
#   OPENAI_API_KEY=your_gateway_key
#   OPENAI_BASE_URL=https://api.lundong.ai

# 3. Start all services
docker compose up -d

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Seed LEGO car set data (140 sets)
docker compose exec backend python /app/data/seed_sets.py

# 6. Open the app
open http://localhost:3000
```

### Lightning Dev Mode (SQLite, No Docker)

```bash
cd backend
pip install -r requirements.txt

# Start with SQLite (no PostgreSQL/Redis needed)
DATABASE_URL="sqlite+aiosqlite:///dev.db" REDIS_URL="" GENERATION_MODE=auto \
  OPENAI_API_KEY="your_gateway_key" OPENAI_BASE_URL="https://api.lundong.ai" \
  uvicorn app.main:app --port 8000

# API docs → http://localhost:8000/docs
```

---

## 📡 API Endpoints

### Design Generation
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/designs` | Create design (text: make+model+year + scale) |
| `POST` | `/api/v1/designs/from-image` | Create design (image upload → vision analysis) |
| `GET` | `/api/v1/designs/{id}` | Design detail + parts + match info |
| `GET` | `/api/v1/designs/{id}/status` | Poll async generation status |
| `GET` | `/api/v1/designs/{id}/pricing` | Reference pricing for parts |

### Export
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/export/xml/{id}` | BrickLink Wanted List XML |
| `GET` | `/api/v1/export/csv/{id}` | Parts list CSV |
| `GET` | `/api/v1/export/ldr/{id}` | LDraw .ldr file |
| `GET` | `/api/v1/export/io/{id}` | Studio .io file |

### Community & Reference
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/community` | Browse community mods |
| `POST` | `/api/v1/community/submit` | Submit a community mod |
| `GET` | `/api/v1/templates` | 6 car body templates |
| `GET` | `/api/v1/mods` | 24 mod parts catalog |
| `GET` | `/api/v1/sets/known-cars` | 140 known LEGO car sets |
| `GET` | `/api/v1/cars/lookup` | Validate car via NHTSA API |

---

## 🗂️ Project Structure

```
Car2LEGO/
├── backend/
│   ├── app/
│   │   ├── agents/                # LangGraph agent graphs (3)
│   │   │   ├── design_graph.py    # Text → .io generation
│   │   │   ├── vision_graph.py    # Image → features extraction
│   │   │   └── customization_graph.py  # Design + mod → custom .io
│   │   ├── api/v1/                # REST endpoints (11 routers)
│   │   │   ├── designs.py         # Core design creation API
│   │   │   ├── export.py          # File export (XML/CSV/LDraw/.io)
│   │   │   ├── community.py       # Mod repository
│   │   │   └── research.py        # Web car research
│   │   ├── services/              # Business logic (15 services)
│   │   │   ├── studio_design_generator.py  # AI → Studio .io pipeline
│   │   │   ├── vision_analyzer.py          # Image → car features
│   │   │   ├── matching_engine.py          # L1→L4 cascade (9 flagship specs)
│   │   │   ├── vehicle_taxonomy.py         # 52 sub-styles, 80+ features
│   │   │   ├── studio_templates.py         # 6 chassis LDraw templates
│   │   │   ├── pricing_service.py          # BrickLink reference prices
│   │   │   └── car_research.py             # 70+ brand web search
│   │   ├── integrations/          # External API clients
│   │   │   ├── provider.py        # Abstract LLM provider + key masking
│   │   │   ├── providers/         # DeepSeek / Doubao / Anthropic / OpenAI
│   │   │   ├── llm.py             # Provider-agnostic design client
│   │   │   └── rebrickable.py     # Rebrickable API (L1 parts)
│   │   ├── models/                # SQLAlchemy models (6)
│   │   └── tasks/                 # Celery async task definitions
│   ├── alembic/                   # Database migrations
│   ├── tests/                     # 59 unit tests + integration tests
│   └── requirements.txt
├── frontend/                      # Next.js 14 (App Router)
│   ├── app/
│   │   ├── designs/[id]/          # Design detail page
│   │   └── sets/                  # Known LEGO sets browser
│   └── components/                # React UI components
├── ai/                            # Voxelization pipeline
├── data/                          # Seed data scripts (140 LEGO sets)
├── docs/                          # Documentation
└── docker-compose.yml             # 4-service orchestration
```

---

## 📊 Testing

```bash
cd backend
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite --quiet

# Unit tests (59 tests, 5 modules)
python -m pytest tests/unit/ -v

# With coverage
python -m pytest tests/unit/ -v --cov=app --cov-report=term-missing

# Integration tests
python -m pytest tests/integration/ -v
```

**Test Coverage**: Matching Engine (9), Pricing (13), Color Service (11), LDraw Service (11), Vehicle Taxonomy (15)

**CI**: `.github/workflows/ci.yml` — backend tests (Python 3.11/3.12) + frontend lint on push/PR.

---

## 🔮 Roadmap

- [ ] Three.js 3D preview in browser (real-time .io rendering)
- [ ] Direct BrickLink one-click parts ordering
- [ ] AI building instruction step-by-step generation
- [ ] Mobile app with AR preview (ARKit/ARCore)
- [ ] Multi-angle car photo upload (front/side/rear)
- [ ] Real-time collaborative design editing
- [ ] Rebrickable social integration (share your design)

---

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a PR. For community mod submissions, use the `/api/v1/community/submit` endpoint.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file.

---

<div align="center">
  <sub>🧱 Built with bricks, powered by AI</sub>
</div>
