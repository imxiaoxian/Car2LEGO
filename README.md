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
  LangGraph Agent · Multi-Vendor LLM · 4-Level Matching · Studio .io Output · Community Mods
</p>

</div>

---

## 📖 Overview

**Car2LEGO** converts any car model into **BrickLink Studio `.io` files** — complete with parts lists, building instructions, and pricing. Just input a car make, model, and year (or upload a photo), and the platform generates LEGO blueprints you can open directly in BrickLink Studio 2.0 for 3D viewing, photorealistic rendering, and parts export.

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
│  │  (Doubao)       │  │  (Web Search) │  │  (XML/CSV/LDraw)  │     │
│  └────────────────┘  └──────────────┘  └──────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌───────────────┐
│PostgreSQL│  │  Redis   │  │  Celery Worker│  │  AI Providers │
│          │  │ (Broker) │  │  (Async Gen)  │  │  (Multi-Vendor)│
└──────────┘  └──────────┘  └──────────────┘  └───────────────┘
                                                     │
                                    ┌────────────────┼────────────────┐
                                    ▼                ▼                ▼
                                DeepSeek          Doubao          Anthropic
                                (Text/Design)     (Vision)        (Fallback)
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

### 🤖 Multi-Vendor AI Provider System

Abstract LLM provider layer with runtime switching:

| Provider | Role | Model |
|----------|------|-------|
| **DeepSeek** | Text → LEGO design generation (L4) | deepseek-chat / v4-pro |
| **Doubao** (Volcano Engine) | Vision → Car image analysis | doubao-seed-2-1-pro |
| **Anthropic** | Legacy fallback | Claude Sonnet 4 |

> 🔒 **Security-first**: All API keys are masked in logs via `mask_api_key()` — real keys stored only in private `_api_key` attributes.

### 📐 Scale System

| Scale | AI Generation | Parts Source | Example Sets |
|-------|:---:|-------------|--------------|
| **1:38** | ✅ | AI (20-40 parts, 200-350 total) | Speed Champions 76919, 76920 |
| **1:12** | ❌ | Rebrickable import | Creator Expert 10295, 10337 |
| **1:10** | ❌ | Rebrickable import | Technic 42154, 42156 |
| **1:8** | ❌ | Rebrickable import | Ultimate 42115, 42143, 42172 |

### 🏪 Community Mod System
- **MOD_SPEC v1.0** format with versioning
- 24 built-in real-world mods (GT wings, widebody kits, etc.)
- 80-part curated LEGO parts knowledge catalog
- Steam Workshop-style submission/browse functionality

### 🔍 Web Research Pipeline
- 70+ manufacturer domains mapped (byd.com → porsche.com)
- Prioritized search queries (official site → Wikipedia → auto sites)
- Structured car specs extraction for design generation

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
| **LLM** | DeepSeek + Doubao + Anthropic | Multi-vendor with unified provider interface |
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
- DeepSeek API Key
- Doubao API Key (for vision features)

### Installation

```bash
# 1. Clone
git clone https://github.com/imxiaoxian/Car2LEGO.git
cd Car2LEGO

# 2. Configure
cp .env.example .env
# Edit .env with your API keys:
#   DEEPSEEK_API_KEY=sk-your-key
#   DOUBAO_API_KEY=ark-your-key

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
pip install fastapi uvicorn sqlalchemy aiosqlite anthropic httpx celery redis alembic --quiet

# Start with SQLite (no PostgreSQL/Redis needed)
DATABASE_URL="sqlite+aiosqlite:///test.db" REDIS_URL="" GENERATION_MODE=sync \
  DEEPSEEK_API_KEY="sk-your-key" DOUBAO_API_KEY="ark-your-key" \
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
