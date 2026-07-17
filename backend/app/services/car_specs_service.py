"""CarSpecsService — query, persist, and format real-world car specs.

Acts as the bridge between the CarSpec DB table (knowledge base) and the
LLM design generator. Used by `build_prompt_node` to inject accurate car
dimensions and features into the LLM prompt.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.car_spec import CarSpec
from app.services.car_research import CarResearchResult


# LDU conversion: 1:38 scale, 1 LDU = 0.4 mm
# model_ldu = real_mm / 38 / 0.4 = real_mm / 15.2
LDU_DIVISOR = 15.2


class CarSpecsService:
    """Query and persist car specifications for the LLM design generator."""

    @staticmethod
    async def get_specs(db: AsyncSession, make: str, model: str, year: int) -> CarSpec | None:
        """Look up car specs by make+model+year.

        Tries exact match first, then falls back to same make+model with
        nearest year (±3 years) for same-generation vehicles.
        """
        # Exact match
        result = await db.execute(
            select(CarSpec).where(
                CarSpec.make == make,
                CarSpec.model == model,
                CarSpec.year == year,
            )
        )
        specs = result.scalar_one_or_none()
        if specs:
            return specs

        # Fuzzy year: same make+model, nearest year within ±3
        result = await db.execute(
            select(CarSpec)
            .where(
                CarSpec.make == make,
                CarSpec.model == model,
            )
            .order_by(CarSpec.year.asc())
        )
        candidates = result.scalars().all()
        if not candidates:
            return None

        # Find nearest year within ±3
        nearest = min(
            candidates,
            key=lambda s: abs(s.year - year),
        )
        if abs(nearest.year - year) <= 3:
            return nearest
        return None

    @staticmethod
    async def save_specs(db: AsyncSession, result: CarResearchResult) -> CarSpec:
        """Persist a CarResearchResult into the car_specs table.

        If an entry with the same make+model+year exists, update it;
        otherwise create a new one.
        """
        existing_result = await db.execute(
            select(CarSpec).where(
                CarSpec.make == result.make,
                CarSpec.model == result.model,
                CarSpec.year == result.year,
            )
        )
        specs = existing_result.scalar_one_or_none()

        dims = result.dimensions or {}
        length_mm = dims.get("length_mm")
        width_mm = dims.get("width_mm")
        height_mm = dims.get("height_mm")
        wheelbase_mm = dims.get("wheelbase_mm")

        if specs:
            # Update existing entry
            specs.body_style = result.body_style or specs.body_style
            specs.length_mm = length_mm or specs.length_mm
            specs.width_mm = width_mm or specs.width_mm
            specs.height_mm = height_mm or specs.height_mm
            specs.wheelbase_mm = wheelbase_mm or specs.wheelbase_mm
            specs.engine_type = result.engine_type or specs.engine_type
            specs.drive_type = result.drive_type or specs.drive_type
            specs.distinctive_features = result.distinctive_features or specs.distinctive_features
            specs.colors_available = result.colors_available or specs.colors_available
            specs.source = result.source or specs.source
            specs.confidence = result.confidence or specs.confidence
        else:
            specs = CarSpec(
                make=result.make,
                model=result.model,
                year=result.year,
                body_style=result.body_style or None,
                length_mm=length_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                wheelbase_mm=wheelbase_mm,
                engine_type=result.engine_type or None,
                drive_type=result.drive_type or None,
                horsepower=None,
                top_speed_kmh=None,
                distinctive_features=result.distinctive_features or None,
                colors_available=result.colors_available or None,
                body_proportions=None,
                source=result.source or None,
                confidence=result.confidence or None,
            )
            db.add(specs)

        await db.flush()
        return specs

    @staticmethod
    async def get_or_research(
        db: AsyncSession, make: str, model: str, year: int
    ) -> CarSpec | None:
        """Query DB for car specs. Returns None if not found.

        Web research + persistence is handled separately by
        CarResearchService.research_and_save() (Phase 4).
        """
        return await CarSpecsService.get_specs(db, make, model, year)

    @staticmethod
    def specs_to_prompt_section(specs: CarSpec) -> str:
        """Convert CarSpec into an LLM prompt section.

        Includes real dimensions, 1:38 scale LDU conversion, engine info,
        body proportions, distinctive features, and available colors.
        """
        lines = [f"## Real Car Specifications ({specs.year} {specs.make} {specs.model})"]

        # Dimensions + LDU conversion
        dim_parts = []
        ldu_parts = []
        if specs.length_mm:
            dim_parts.append(f"{specs.length_mm}mm (L)")
            ldu_parts.append(f"{int(specs.length_mm / LDU_DIVISOR)} LDU (L)")
        if specs.width_mm:
            dim_parts.append(f"{specs.width_mm}mm (W)")
            ldu_parts.append(f"{int(specs.width_mm / LDU_DIVISOR)} LDU (W)")
        if specs.height_mm:
            dim_parts.append(f"{specs.height_mm}mm (H)")
            ldu_parts.append(f"{int(specs.height_mm / LDU_DIVISOR)} LDU (H)")

        if dim_parts:
            lines.append(f"- Dimensions: {' × '.join(dim_parts)}")
            lines.append(f"- 1:38 Scale LDU: {' × '.join(ldu_parts)}")
        if specs.wheelbase_mm:
            wb_ldu = int(specs.wheelbase_mm / LDU_DIVISOR)
            lines.append(f"- Wheelbase: {specs.wheelbase_mm}mm ({wb_ldu} LDU)")

        # Engine and drivetrain
        engine_parts = []
        if specs.engine_type:
            engine_parts.append(specs.engine_type)
        if specs.horsepower:
            engine_parts.append(f"{specs.horsepower} hp")
        if engine_parts:
            lines.append(f"- Engine: {', '.join(engine_parts)}")
        if specs.drive_type:
            lines.append(f"- Drive: {specs.drive_type}")
        if specs.top_speed_kmh:
            lines.append(f"- Top speed: {specs.top_speed_kmh} km/h")

        # Body proportions
        if specs.body_proportions:
            lines.append(f"- Body: {specs.body_proportions}")

        # Distinctive features
        if specs.distinctive_features:
            features = ", ".join(specs.distinctive_features)
            lines.append(f"- Distinctive features: {features}")

        # Available colors
        if specs.colors_available:
            colors = ", ".join(specs.colors_available)
            lines.append(f"- Available colors: {colors}")

        lines.append("")
        lines.append(
            "Match the real car proportions and features above in your "
            "recolor_rules and extra_parts. Use the LDU dimensions to calibrate "
            "part placement — Speed Champions 8-wide is typically 280-320 LDU long."
        )

        return "\n".join(lines)
