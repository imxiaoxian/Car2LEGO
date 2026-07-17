"""Unit tests for MatchingEngine — L1→L4 cascade."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.matching_engine import MatchingEngine, MatchResult
from tests.conftest import create_test_set


class TestMatchResult:
    """MatchResult dataclass tests."""

    def test_is_immediate_L1(self):
        r = MatchResult(level=1, label="L1", confidence=0.9)
        assert r.is_immediate is True
        assert r.needs_ai_generation is False

    def test_is_immediate_L2(self):
        r = MatchResult(level=2, label="L2", confidence=0.8)
        assert r.is_immediate is True

    def test_is_immediate_L3(self):
        r = MatchResult(level=3, label="L3", confidence=0.6)
        assert r.is_immediate is True

    def test_is_immediate_L4(self):
        r = MatchResult(level=4, label="L4", confidence=0.25)
        assert r.is_immediate is False
        assert r.needs_ai_generation is True

    def test_metadata_defaults(self):
        r = MatchResult(level=4, label="AI", confidence=0.25)
        assert r.metadata == {}


class TestMatchingEngine:
    """Tests for the 4-level matching cascade."""

    async def test_L1_match_exact_make_and_model(
        self, db: AsyncSession
    ):
        """L1 should match when make+model are in the database."""
        await create_test_set(db, set_num="TEST-L1-001", car_make="Porsche",
                              car_model="911 Turbo")
        engine = MatchingEngine(db)
        result = await engine.match("Porsche", "911", 2020)
        assert result is not None
        assert result.level == 1
        assert result.label == "Official LEGO Set"
        assert result.set_num == "TEST-L1-001"

    async def test_L1_no_match_unknown_car(
        self, db: AsyncSession
    ):
        """L1 should return None for cars not in the database."""
        engine = MatchingEngine(db)
        result = await engine.match("UnknownBrand", "UnknownModel", 2024)
        assert result.level == 4  # falls through to L4
        assert result.needs_ai_generation is True

    async def test_L1_case_insensitive(
        self, db: AsyncSession
    ):
        """L1 matching should be case-insensitive."""
        await create_test_set(db, set_num="TEST-L1-002", car_make="Porsche",
                              car_model="911 Turbo")
        engine = MatchingEngine(db)
        result = await engine.match("porsche", "911 turbo", 2020)
        assert result is not None
        assert result.level == 1

    async def test_L1_year_proximity_bonus(
        self, db: AsyncSession
    ):
        """L1 should score higher for closer years."""
        await create_test_set(db, set_num="OLD-1", car_make="Porsche",
                              car_model="911", year=1980)
        await create_test_set(db, set_num="NEW-1", car_make="Porsche",
                              car_model="911", year=2022)
        engine = MatchingEngine(db)
        result = await engine.match("Porsche", "911", 2022)
        # Should prefer the 2022 set over the 1980 set
        assert result.set_num == "NEW-1"

    @pytest.mark.skip(reason="L2 requires Moc table with data — tested in integration")
    async def test_L2_fallback_when_no_L1(self, db: AsyncSession):
        """L2 should be tried when L1 returns nothing."""
        pass

    @pytest.mark.skip(reason="L3 requires Template + Car tables — tested in integration")
    async def test_L3_fallback_when_no_L1_L2(self, db: AsyncSession):
        """L3 should match by body style template."""
        pass

    async def test_L4_always_returns(
        self, db: AsyncSession
    ):
        """L4 should always return a result (never None)."""
        engine = MatchingEngine(db)
        result = await engine.match("TotalUnknown", "Nothing", 2099)
        assert result is not None
        assert result.level == 4
        assert result.label == "AI Generated"
        assert result.confidence == 0.25
        assert result.metadata["make"] == "TotalUnknown"
        assert result.metadata["model"] == "Nothing"
