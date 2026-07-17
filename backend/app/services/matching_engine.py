"""Multi-level car-to-LEGO matching engine.

Implements a 4-level cascade:
  L1: Exact LEGO set match (official sets like Speed Champions)
  L2: Community MOC match
  L3: Category template adaptation
  L4: AI voxel generation (async fallback)

Each level returns a MatchResult with confidence score and metadata.
"""

from dataclasses import dataclass, field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lego_set import LegoSet
from app.models.moc import Moc
from app.models.template import DesignTemplate


# ── Technic Ultimate Car Concept Series — flagship mechanical specs ──
# Used to enrich L1 match metadata for the 6 official 1:8 supercars.
# These specs inform downstream AI generation for more accurate designs.

FLAGSHIP_SPECS: dict[str, dict] = {
    "42056-1": {
        "series": "Technic Ultimate Car Concept",
        "series_index": 1,
        "scale": "1:8",
        "engine": "Flat-6",
        "transmission": "4-speed sequential",
        "doors": "standard",
        "suspension": "independent with red springs",
        "distinctive_features": [
            "adjustable rear spoiler",
            "opening hood with suitcase in frunk",
            "collector's book with unique serial number",
            "RS-style spoked rims",
        ],
        "real_hp": 500,
        "real_top_speed_kmh": 312,
        "body_proportions": "rear-engine, wide rear hips, sloping roofline, large fixed rear wing",
    },
    "42083-1": {
        "series": "Technic Ultimate Car Concept",
        "series_index": 2,
        "scale": "1:8",
        "engine": "W16",
        "transmission": "8-speed sequential with paddle shifters",
        "doors": "standard",
        "suspension": "independent",
        "distinctive_features": [
            "active rear wing (deployable via top speed key)",
            "W16 engine with visible moving pistons",
            "spoked rims with Bugatti emblem",
            "front trunk with Bugatti overnight bag",
            "duo-tone blue color scheme",
        ],
        "real_hp": 1500,
        "real_top_speed_kmh": 420,
        "body_proportions": "mid-engine, C-shaped side profile line, horseshoe grille, low wide stance",
    },
    "42115-1": {
        "series": "Technic Ultimate Car Concept",
        "series_index": 3,
        "scale": "1:8",
        "engine": "V12",
        "transmission": "8-speed sequential with paddle shifters",
        "doors": "scissor",
        "suspension": "4-wheel independent with pushrod front",
        "distinctive_features": [
            "scissor doors (rotate upward at 90-degree angle)",
            "golden rims with Lamborghini center caps",
            "Y-style LED headlight and taillight shapes",
            "hexagonal design motifs in body panels",
            "lime green (Verde Mantis) body color",
        ],
        "real_hp": 819,
        "real_top_speed_kmh": 350,
        "body_proportions": "mid-engine, wedge profile, hexagonal side intakes, triple exhaust, low nose",
    },
    "42143-1": {
        "series": "Technic Ultimate Car Concept",
        "series_index": 4,
        "scale": "1:8",
        "engine": "V12",
        "transmission": "8-speed sequential with paddle shifters",
        "doors": "butterfly",
        "suspension": "independent with shock absorbers",
        "distinctive_features": [
            "butterfly doors (hinged at A-pillar, open upward and forward)",
            "chrome-painted drum-lacquered silver rims",
            "removable targa-style roof panel",
            "horizontal blade taillight spanning full width",
            "classic Rosso Corsa red body",
        ],
        "real_hp": 840,
        "real_top_speed_kmh": 340,
        "body_proportions": "mid-engine, curved aerodynamic body, flying buttress rear, low aggressive stance",
    },
    "42172-1": {
        "series": "Technic Ultimate Car Concept",
        "series_index": 5,
        "scale": "1:8",
        "engine": "V8",
        "transmission": "7-speed sequential with dual-clutch paddle shifters",
        "doors": "butterfly",
        "suspension": "independent",
        "distinctive_features": [
            "butterfly doors with spring-loaded shock absorber mechanism",
            "adjustable rear wing (active aero, deploys at speed)",
            "paddle shifters behind steering wheel",
            "E-mode / hybrid gear selector stick",
            "McLaren signature papaya orange body",
        ],
        "real_hp": 903,
        "real_top_speed_kmh": 350,
        "body_proportions": "mid-engine, teardrop cabin, large side air intakes, low drag coefficient 0.34",
    },
    "42232-1": {
        "series": "Technic Ultimate Car Concept",
        "series_index": 6,
        "scale": "1:8",
        "engine": "V8",
        "transmission": "9-speed sequential (Light Speed Transmission)",
        "doors": "dihedral synchro-helix",
        "suspension": "Triplex (front and rear, third damper for anti-squat)",
        "distinctive_features": [
            "Ghost Mode: one-motion simultaneous door/hood/mirror opening",
            "rotating gear indicator disc showing current gear",
            "foldable side mirrors with orange accent",
            "removable roof panel",
            "all printed parts — zero stickers",
            "black body with orange accent stripes",
        ],
        "real_hp": 1602,
        "real_top_speed_kmh": 480,
        "body_proportions": "mid-engine, long tail, active rear wing, dihedral doors, extreme low profile",
    },
    # ── Premium 1:8 Technic (non-UCCS flagships) ──
    "42156-1": {
        "series": "Technic Ultimate Car Concept (Le Mans)",
        "series_index": None,
        "scale": "1:10",
        "engine": "V6 twin-turbo hybrid",
        "transmission": "7-speed sequential",
        "doors": "standard (butterfly-hinged canopy)",
        "suspension": "pushrod front and rear",
        "distinctive_features": [
            "Le Mans Hypercar (LMH) aero package with massive rear wing",
            "hybrid powertrain with visible electric motor",
            "tricolor Peugeot Sport livery stripes",
            "low-drag long-tail body",
            "illuminated Peugeot lion badge",
        ],
        "real_hp": 680,
        "real_top_speed_kmh": 340,
        "body_proportions": "mid-engine Le Mans prototype, long tail, dorsal fin, massive diffuser",
    },
    "42206-1": {
        "series": "Technic 1:8 F1 Series",
        "series_index": None,
        "scale": "1:8",
        "engine": "V6 turbo hybrid (Honda RBPT)",
        "transmission": "8-speed semi-automatic",
        "doors": "none (open cockpit)",
        "suspension": "pushrod front, pullrod rear",
        "distinctive_features": [
            "dark blue/red Oracle Red Bull Racing livery",
            "printed Pirelli tires with authentic markings",
            "DRS (Drag Reduction System) movable rear wing",
            "Halo cockpit protection device",
            "detailed sidepod undercut aero",
        ],
        "real_hp": 1000,
        "real_top_speed_kmh": 350,
        "body_proportions": "open-wheel F1, long wheelbase, complex bargeboard aero, low nose",
    },
    "42207-1": {
        "series": "Technic 1:8 F1 Series",
        "series_index": None,
        "scale": "1:8",
        "engine": "V6 turbo hybrid (Ferrari 066/12)",
        "transmission": "8-speed semi-automatic",
        "doors": "none (open cockpit)",
        "suspension": "pushrod front, pullrod rear",
        "distinctive_features": [
            "classic Rosso Corsa red Ferrari livery with yellow accents",
            "printed Pirelli tires with yellow Ferrari branding",
            "adjustable rear spoiler (DRS activated)",
            "opening engine cover revealing V6 engine with rotating MGU-H",
            "2-speed gearbox mechanism",
        ],
        "real_hp": 1000,
        "real_top_speed_kmh": 350,
        "body_proportions": "open-wheel F1, scalloped sidepods, distinctive Ferrari nose, sculpted engine cover",
    },
}


def _enrich_flagship_metadata(set_num: str | None, metadata: dict) -> dict:
    """If the matched set is a Technic flagship, add its mechanical specs to metadata."""
    if set_num and set_num in FLAGSHIP_SPECS:
        metadata["flagship"] = FLAGSHIP_SPECS[set_num]
    return metadata


@dataclass
class MatchResult:
    level: int
    label: str
    confidence: float
    set_num: str | None = None
    set_name: str | None = None
    moc_name: str | None = None
    moc_author: str | None = None
    template_id: str | None = None
    template_name: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def is_immediate(self) -> bool:
        """True if the match can be served immediately (L1-L3)."""
        return self.level < 4

    @property
    def needs_ai_generation(self) -> bool:
        """True if AI generation is needed (L4)."""
        return self.level == 4


class MatchingEngine:
    """Orchestrates the 4-level car-to-LEGO matching cascade."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def match(self, make: str, model: str, year: int) -> MatchResult:
        """Run the full matching cascade and return the best result.

        L1 -> L2 -> L3 -> L4 (each only runs if previous fails).
        """
        # Level 1: Official LEGO set
        result = await self._match_level1(make, model, year)
        if result:
            return result

        # Level 2: Community MOC
        result = await self._match_level2(make, model, year)
        if result:
            return result

        # Level 3: Category template
        result = await self._match_level3(make, model, year)
        if result:
            return result

        # Level 4: AI voxel generation
        return self._match_level4(make, model, year)

    # ── L1: Official LEGO Sets ──────────────────────────

    async def _match_level1(
        self, make: str, model: str, year: int
    ) -> MatchResult | None:
        """Search for official LEGO sets matching the car."""
        stmt = select(LegoSet).where(
            func.lower(LegoSet.car_make) == make.lower(),
            func.lower(LegoSet.car_model).contains(model.lower()),
        )
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()

        if not candidates:
            return None

        # Score by year proximity
        best = None
        best_score = -1.0
        for c in candidates:
            score = 0.5  # base score for make+model match
            if c.year and year:
                year_diff = abs(c.year - year)
                score += max(0, 1.0 - year_diff / 50.0)
            if c.year == year:
                score += 0.5  # exact year bonus
            if score > best_score:
                best_score = score
                best = c

        if best and best_score > 0.3:
            metadata = _enrich_flagship_metadata(best.set_num, {})
            return MatchResult(
                level=1,
                label="Official LEGO Set",
                confidence=min(best_score, 1.0),
                set_num=best.set_num,
                set_name=best.name,
                metadata=metadata,
            )

        return None

    # ── L2: Community MOCs ──────────────────────────────

    async def _match_level2(
        self, make: str, model: str, year: int
    ) -> MatchResult | None:
        """Search community MOCs for the car model."""
        stmt = (
            select(Moc)
            .where(
                func.lower(Moc.car_make) == make.lower(),
                func.lower(Moc.car_model).contains(model.lower()),
            )
            .order_by(Moc.rating.desc().nulls_last())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        moc = result.scalar_one_or_none()

        if moc:
            confidence = 0.85 if moc.rating and moc.rating >= 4.0 else 0.75
            return MatchResult(
                level=2,
                label="Community Design (MOC)",
                confidence=confidence,
                moc_name=moc.name,
                moc_author=moc.author,
            )

        return None

    # ── L3: Category Templates ──────────────────────────

    async def _match_level3(
        self, make: str, model: str, year: int
    ) -> MatchResult | None:
        """Match by car body style category template."""
        # Look up car body_style from DB, default to sedan
        from app.models.car import Car
        car_stmt = select(Car).where(
            func.lower(Car.make) == make.lower(),
            func.lower(Car.model).contains(model.lower()),
        )
        car_result = await self.db.execute(car_stmt)
        car = car_result.scalar_one_or_none()
        body_style = car.body_style if car and car.body_style else "sedan"

        stmt = select(DesignTemplate).where(
            func.lower(DesignTemplate.body_style) == body_style
        )
        result = await self.db.execute(stmt)
        template = result.scalar_one_or_none()

        if template:
            return MatchResult(
                level=3,
                label="Category Template",
                confidence=0.60,
                template_id=str(template.id),
                template_name=template.name,
            )

        # Fallback: try any template
        stmt = select(DesignTemplate).limit(1)
        result = await self.db.execute(stmt)
        template = result.scalar_one_or_none()

        if template:
            return MatchResult(
                level=3,
                label="Generic Template",
                confidence=0.40,
                template_id=str(template.id),
                template_name=template.name,
            )

        return None

    # ── L4: AI Generation ───────────────────────────────

    def _match_level4(self, make: str, model: str, year: int) -> MatchResult:
        """AI voxel generation fallback — returns immediately with pending status."""
        return MatchResult(
            level=4,
            label="AI Generated",
            confidence=0.25,
            metadata={
                "make": make,
                "model": model,
                "year": year,
            },
        )
