"""Car research API — searches the web for unknown car models.

Priority: Official manufacturer sites → Wikipedia → Automotive databases.

When a car is not in our database, this endpoint gathers high-quality
specifications from the web to enable accurate LEGO design generation.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.car_research import CarResearchService

router = APIRouter()


class ResearchRequest(BaseModel):
    make: str = Field(..., examples=["BYD"])
    model: str = Field(..., examples=["Han EV"])
    year: int = Field(default=2024, examples=[2024])


class ResearchResponse(BaseModel):
    make: str
    model: str
    year: int
    official_domain: str | None = None
    search_queries: list[dict] = []
    suggested_sources: list[str] = []
    research_notes: str = ""


class TaxonomySuggestion(BaseModel):
    category: str
    suggested_id: str
    suggested_label: str
    description: str
    similar_existing: str = ""


@router.post("", response_model=ResearchResponse)
async def research_car(req: ResearchRequest):
    """Research an unknown car model.

    Returns search queries and known sources for this car. The actual web
    research happens via Claude Code's WebSearch, which feeds data back
    into the design generation pipeline.
    """
    official_domain = CarResearchService.get_official_domain(req.make)

    queries = CarResearchService.build_search_queries(req.make, req.model, req.year)

    # Build suggested source URLs
    sources = []
    if official_domain:
        sources.append(f"https://www.{official_domain}/")

    # Wikipedia — reliable for most cars
    wiki_title = f"{req.make}_{req.model}".replace(" ", "_")
    sources.append(f"https://en.wikipedia.org/wiki/{wiki_title}")

    # Automotive databases
    car_slug = f"{req.make.lower()}-{req.model.lower()}-{req.year}".replace(" ", "-")
    sources.append(f"https://www.caranddriver.com/{req.make.lower()}/{req.model.lower()}")
    sources.append(f"https://www.autoevolution.com/cars/{car_slug}.html")
    sources.append(f"https://www.netcarshow.com/{req.make.lower()}/{req.year}-{req.model.lower()}/")
    sources.append(f"https://www.ultimatecarpage.com/spec/{car_slug}.html")

    notes = f"""Research plan for {req.year} {req.make} {req.model}:

1. OFFICIAL SITE (highest priority): {official_domain or 'Not in known list — try searching "[make] official website"'}
2. WIKIPEDIA: Check en.wikipedia.org for specifications, dimensions, images
3. AUTOMOTIVE SITES: caranddriver.com, autoevolution.com, netcarshow.com
4. SEARCH QUERIES (in priority order):
{chr(10).join(f'   - [{q["priority"]}] {q["query"]} ({q["purpose"]})' for q in queries)}

Key data to extract:
- Body dimensions (length/width/height in mm) → map to LEGO stud scale
- Body style classification
- Distinctive design features (grille, headlights, body lines)
- Factory paint colors → map to LEGO color IDs
- Wheel design and size
"""

    return ResearchResponse(
        make=req.make,
        model=req.model,
        year=req.year,
        official_domain=official_domain,
        search_queries=[
            {"query": q["query"], "priority": q["priority"], "purpose": q["purpose"]}
            for q in queries
        ],
        suggested_sources=sources,
        research_notes=notes,
    )


# In-memory storage for taxonomy suggestions from Vision analyses
_taxonomy_suggestions: list[dict] = []


def collect_taxonomy_suggestions(suggestions: list[dict]):
    """Called after Vision analysis to accumulate novel vehicle types."""
    global _taxonomy_suggestions
    for s in suggestions:
        if not any(e.get("suggested_id") == s.get("suggested_id") for e in _taxonomy_suggestions):
            _taxonomy_suggestions.append(s)


@router.get("/taxonomy-suggestions", response_model=list[TaxonomySuggestion])
async def get_taxonomy_suggestions():
    """Get accumulated taxonomy expansion suggestions from Vision analyses."""
    return _taxonomy_suggestions


@router.post("/taxonomy-suggestions/clear")
async def clear_taxonomy_suggestions():
    """Clear suggestions after reviewing/merging them into taxonomy."""
    global _taxonomy_suggestions
    count = len(_taxonomy_suggestions)
    _taxonomy_suggestions = []
    return {"cleared": count}
