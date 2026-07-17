"""Unit tests for CarSpecsService — query, persist, and format car specs."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.car_spec import CarSpec
from app.services.car_research import CarResearchResult
from app.services.car_specs_service import CarSpecsService


class TestGetSpecs:
    """CarSpecsService.get_specs — DB query logic."""

    async def test_get_specs_exact_match(self, db: AsyncSession):
        """Exact make+model+year match should return the spec."""
        spec = CarSpec(
            make="Porsche",
            model="911 GT3",
            year=2023,
            body_style="sports_car",
            length_mm=4573,
            width_mm=1852,
            height_mm=1279,
            wheelbase_mm=2457,
            engine_type="4.0L Flat-6",
            drive_type="RWD",
            horsepower=502,
            top_speed_kmh=318,
            distinctive_features=["round headlights", "rear wing"],
            colors_available=["White", "Yellow"],
            body_proportions="rear-engine, sloping roofline",
        )
        db.add(spec)
        await db.flush()

        result = await CarSpecsService.get_specs(db, "Porsche", "911 GT3", 2023)

        assert result is not None
        assert result.make == "Porsche"
        assert result.model == "911 GT3"
        assert result.year == 2023
        assert result.length_mm == 4573
        assert result.horsepower == 502
        assert "round headlights" in result.distinctive_features

    async def test_get_specs_fuzzy_year(self, db: AsyncSession):
        """Same make+model, different year within ±3 should fuzzy match."""
        spec = CarSpec(
            make="Ferrari",
            model="488 GTB",
            year=2016,
            body_style="sports_car",
            length_mm=4568,
        )
        db.add(spec)
        await db.flush()

        # Query for 2018, DB has 2016 → within ±3
        result = await CarSpecsService.get_specs(db, "Ferrari", "488 GTB", 2018)

        assert result is not None
        assert result.year == 2016  # returns the DB entry

    async def test_get_specs_fuzzy_year_out_of_range(self, db: AsyncSession):
        """Same make+model, but year difference >3 should not match."""
        spec = CarSpec(
            make="Ferrari",
            model="F40",
            year=1992,
            body_style="sports_car",
            length_mm=4430,
        )
        db.add(spec)
        await db.flush()

        # Query for 2020, DB has 1992 → difference >3
        result = await CarSpecsService.get_specs(db, "Ferrari", "F40", 2020)

        assert result is None

    async def test_get_specs_not_found(self, db: AsyncSession):
        """Unknown car should return None."""
        result = await CarSpecsService.get_specs(db, "Unknown", "Model", 2024)
        assert result is None

    async def test_get_specs_case_sensitive_make(self, db: AsyncSession):
        """Make matching is case-sensitive (exact match required)."""
        spec = CarSpec(
            make="BMW",
            model="M3",
            year=2022,
            body_style="sedan",
        )
        db.add(spec)
        await db.flush()

        # Exact case
        result = await CarSpecsService.get_specs(db, "BMW", "M3", 2022)
        assert result is not None

        # Different case should not match
        result_lower = await CarSpecsService.get_specs(db, "bmw", "M3", 2022)
        assert result_lower is None


class TestSaveSpecs:
    """CarSpecsService.save_specs — persistence logic."""

    async def test_save_specs_creates_new(self, db: AsyncSession):
        """New CarResearchResult should create a CarSpec entry."""
        result = CarResearchResult(
            make="McLaren",
            model="720S",
            year=2019,
            body_style="sports_car",
            dimensions={
                "length_mm": 4544,
                "width_mm": 1930,
                "height_mm": 1196,
                "wheelbase_mm": 2670,
            },
            engine_type="4.0L Twin-Turbo V8",
            drive_type="RWD",
            distinctive_features=["dihedral doors"],
            colors_available=["Orange"],
            source="wikipedia",
            confidence=0.9,
        )

        spec = await CarSpecsService.save_specs(db, result)

        assert spec.id is not None
        assert spec.make == "McLaren"
        assert spec.model == "720S"
        assert spec.length_mm == 4544
        assert spec.engine_type == "4.0L Twin-Turbo V8"
        assert spec.distinctive_features == ["dihedral doors"]
        assert spec.horsepower is None  # CarResearchResult doesn't carry this

    async def test_save_specs_updates_existing(self, db: AsyncSession):
        """Existing make+model+year should be updated, not duplicated."""
        existing = CarSpec(
            make="Audi",
            model="R8",
            year=2022,
            body_style="sports_car",
            length_mm=4400,
            horsepower=600,
        )
        db.add(existing)
        await db.flush()

        result = CarResearchResult(
            make="Audi",
            model="R8",
            year=2022,
            body_style="sports_car",
            dimensions={"length_mm": 4429, "width_mm": 1940},
            engine_type="5.2L V10",
            distinctive_features=["hexagonal grille"],
            source="wikipedia",
            confidence=0.95,
        )

        spec = await CarSpecsService.save_specs(db, result)

        assert spec.id == existing.id  # same record
        assert spec.length_mm == 4429  # updated
        assert spec.width_mm == 1940  # new field added
        assert spec.horsepower == 600  # preserved from existing


class TestSpecsToPromptSection:
    """CarSpecsService.specs_to_prompt_section — LLM prompt formatting."""

    def test_specs_to_prompt_section_full(self):
        """Full spec should produce complete prompt section."""
        spec = CarSpec(
            make="Porsche",
            model="911 GT3",
            year=2023,
            body_style="sports_car",
            length_mm=4573,
            width_mm=1852,
            height_mm=1279,
            wheelbase_mm=2457,
            engine_type="4.0L Flat-6",
            drive_type="RWD",
            horsepower=502,
            top_speed_kmh=318,
            distinctive_features=["round headlights", "rear wing"],
            colors_available=["White", "Yellow"],
            body_proportions="rear-engine, sloping roofline",
        )

        section = CarSpecsService.specs_to_prompt_section(spec)

        assert "Real Car Specifications" in section
        assert "2023 Porsche 911 GT3" in section
        assert "4573mm" in section
        assert "1852mm" in section
        assert "1279mm" in section
        assert "2457mm" in section
        # LDU conversion: 4573 / 15.2 ≈ 300
        assert "LDU" in section
        assert "4.0L Flat-6" in section
        assert "502 hp" in section
        assert "RWD" in section
        assert "318 km/h" in section
        assert "rear-engine" in section
        assert "round headlights" in section
        assert "White" in section
        assert "Yellow" in section

    def test_specs_to_prompt_section_no_dimensions(self):
        """Spec without dimensions should omit LDU conversion."""
        spec = CarSpec(
            make="Unknown",
            model="Concept",
            year=2024,
            body_style="sports_car",
            distinctive_features=["futuristic design"],
            colors_available=["Silver"],
        )

        section = CarSpecsService.specs_to_prompt_section(spec)

        assert "Real Car Specifications" in section
        assert "2024 Unknown Concept" in section
        assert "Scale LDU" not in section  # no dimensions → no LDU conversion
        assert "Dimensions" not in section
        assert "futuristic design" in section
        assert "Silver" in section

    def test_specs_to_prompt_section_minimal(self):
        """Minimal spec (only make+model+year) should still produce valid output."""
        spec = CarSpec(
            make="Tesla",
            model="Cybertruck",
            year=2024,
        )

        section = CarSpecsService.specs_to_prompt_section(spec)

        assert "Real Car Specifications" in section
        assert "2024 Tesla Cybertruck" in section
        # Should end with the guidance line
        assert "Match the real car proportions" in section


class TestGetOrResearch:
    """CarSpecsService.get_or_research — DB query (no web research in this phase)."""

    async def test_get_or_research_found(self, db: AsyncSession):
        """Should return spec when found in DB."""
        spec = CarSpec(
            make="BMW",
            model="M3",
            year=2022,
            body_style="sedan",
            length_mm=4794,
        )
        db.add(spec)
        await db.flush()

        result = await CarSpecsService.get_or_research(db, "BMW", "M3", 2022)

        assert result is not None
        assert result.length_mm == 4794

    async def test_get_or_research_not_found(self, db: AsyncSession):
        """Should return None when not in DB (no web research)."""
        result = await CarSpecsService.get_or_research(db, "Unknown", "Car", 2024)
        assert result is None
