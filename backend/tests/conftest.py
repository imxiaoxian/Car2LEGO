"""Shared test fixtures and configuration for Car2LEGO backend tests."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.car import Car
from app.models.design import Design, DesignPart
from app.models.lego_set import LegoSet
from app.models.moc import Moc
from app.models.part import Part, PartColor
from app.models.template import DesignTemplate
from app.models.user import User


# ── Engine & Session fixtures ──────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///test_unit.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create a fresh event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a test database engine (session-scoped)."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    # Cleanup: drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session, rolled back after each test."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        # Start a transaction that we'll roll back
        await conn.begin_nested()
        async with session_factory(bind=conn) as session:
            # Nested transaction so each test is isolated
            await session.begin_nested()
            yield session
            await session.rollback()


# ── Mock fixtures ──────────────────────────────────────


class MockStructuredRunnable:
    """Mock for the runnable returned by `ChatModel.with_structured_output()`."""

    def __init__(self, output):
        self._output = output

    async def ainvoke(self, messages, config=None):
        return self._output


class MockToolsRunnable:
    """Mock for the runnable returned by `ChatModel.bind_tools()`."""

    def __init__(self, response_message):
        self._response = response_message

    async def ainvoke(self, messages, config=None):
        return self._response


class MockChatModel:
    """Minimal fake LangChain ChatModel for graph tests.

    Patch `app.agents.models.create_text_llm` (or the graph module's import)
    to return an instance of this. `bind_tools()` returns a runnable that
    yields `tool_response` (default: an AIMessage with no tool_calls, so the
    ReAct loop exits after one iteration). `with_structured_output()` returns
    a runnable that yields `structured_output` (a Pydantic model instance).
    """

    def __init__(self, structured_output=None, tool_response=None):
        from langchain_core.messages import AIMessage
        self._structured_output = structured_output
        self._tool_response = tool_response or AIMessage(content="done")

    def bind_tools(self, tools):
        return MockToolsRunnable(self._tool_response)

    def with_structured_output(self, schema):
        return MockStructuredRunnable(self._structured_output)

    async def ainvoke(self, messages, config=None):
        return self._tool_response


@pytest.fixture
def mock_chat_model():
    """Factory fixture: build a MockChatModel with preset outputs.

    Usage:
        llm = mock_chat_model(structured_output=some_pydantic_instance)
    """
    def _make(structured_output=None, tool_response=None):
        return MockChatModel(
            structured_output=structured_output,
            tool_response=tool_response,
        )
    return _make


@pytest.fixture
def mock_studio_design():
    """Return a valid StudioDesign Pydantic instance for mocked LLM tests."""
    from app.agents.design_graph import StudioDesign, LegoPartPlacement
    return StudioDesign(
        design_notes="Mocked design for a sports car.",
        total_parts=3,
        body_color_id=4,
        parts=[
            LegoPartPlacement(
                part_num="3024.dat", bricklink_id="3024", color_id=4,
                color_name="Red", x=0, y=-24, z=0, quantity=1, step=1,
            ),
            LegoPartPlacement(
                part_num="3005.dat", bricklink_id="3005", color_id=0,
                color_name="Black", x=0, y=-40, z=0, quantity=2, step=1,
            ),
            LegoPartPlacement(
                part_num="3020.dat", bricklink_id="3020", color_id=4,
                color_name="Red", x=0, y=0, z=80, quantity=1, step=2,
            ),
        ],
    )


@pytest.fixture
def mock_customized_design():
    """Return a valid CustomizedDesign Pydantic instance for mocked LLM tests."""
    from app.agents.customization_graph import CustomizedDesign, CustomizedPartPlacement
    return CustomizedDesign(
        modification_summary="Added a rear wing.",
        added_parts_count=1,
        removed_parts_count=0,
        total_parts=3,
        parts=[
            CustomizedPartPlacement(
                part_num="3024.dat", bricklink_id="3024", color_id=4,
                color_name="Red", x=0, y=-24, z=0, quantity=1, change="kept",
            ),
            CustomizedPartPlacement(
                part_num="3005.dat", bricklink_id="3005", color_id=0,
                color_name="Black", x=0, y=-40, z=0, quantity=1, change="kept",
            ),
            CustomizedPartPlacement(
                part_num="3020.dat", bricklink_id="3020", color_id=4,
                color_name="Red", x=0, y=40, z=200, quantity=1, change="added",
            ),
        ],
    )


@pytest.fixture
def mock_design_customization():
    """Return a valid DesignCustomization Pydantic instance for mocked LLM tests.

    This is the Template-First Architecture output: the LLM only produces
    colors + recolor_rules + replace_rules + extra_parts, NOT a full parts list.
    """
    from app.agents.design_graph import DesignCustomization, ExtraPart, RecolorRule, ReplaceRule

    return DesignCustomization(
        body_color_id=4,  # Red (Ferrari)
        accent_color_id=0,  # Black trim
        recolor_rules=[
            RecolorRule(label="body_side", new_color_id=4),
            RecolorRule(label="rear_body", new_color_id=4),
            RecolorRule(label="roof", new_color_id=4),
            RecolorRule(label="hood", new_color_id=4),
            RecolorRule(label="cabin", new_color_id=0),
            RecolorRule(label="bumper", new_color_id=0),
            RecolorRule(label="wheel_arch", new_color_id=0),
            RecolorRule(label="taillight", new_color_id=4),
        ],
        replace_rules=[
            ReplaceRule(
                target_label="headlight",
                new_part_num="4070.dat",
                new_color_id=14,
                rotation="1 0 0 0 1 0 0 0 1",
            ),
        ],
        extra_parts=[
            ExtraPart(
                part_num="3023.dat",
                color_id=0,
                x=40,
                y=96,
                z=20,
                reason="Rear wing support",
            ),
            ExtraPart(
                part_num="44675.dat",
                color_id=0,
                x=20,
                y=96,
                z=15,
                reason="Rear wing element",
            ),
        ],
        design_notes="Red body with black trim. Added rear wing for Ferrari F40.",
    )


@pytest.fixture
def mock_car_features_output():
    """Return a valid CarFeaturesOutput dict (as produced by the vision graph)."""
    return {
        "make": "Ferrari",
        "model": "F40",
        "year": 1987,
        "confidence": "certain",
        "body_style": "sports_car",
        "body_sub_style": "mid_engine_coupe",
        "custom_body_style": "",
        "era": "classic",
        "custom_era": "",
        "region": "euro",
        "custom_region": "",
        "performance_tier": "supercar",
        "custom_performance_tier": "",
        "modification_level": "stock",
        "custom_modification_level": "",
        "primary_color_name": "Rosso Corsa",
        "primary_color_hex": "#D40000",
        "closest_lego_color": 4,
        "closest_lego_color_name": "Red",
        "secondary_colors": [],
        "has_two_tone": False,
        "has_racing_stripes": False,
        "has_carbon_accent": False,
        "custom_color_note": "",
        "estimated_length_studs": 16,
        "estimated_width_studs": 6,
        "estimated_height_bricks": 5,
        "wheel_type": "five_spoke_classic",
        "custom_wheel_type": "",
        "wheel_size_note": "17-inch low profile",
        "aftermarket_wheels": False,
        "brake_caliper_color": "red",
        "wheel_count": 4,
        "front_features": ["pop-up headlights"],
        "rear_features": ["large rear wing"],
        "side_features": ["low side profile"],
        "aero_features": ["rear wing"],
        "roof_features": [],
        "lighting_features": [],
        "ev_features": [],
        "custom_features": [],
        "unusual_attributes": [],
        "is_concept_vehicle": False,
        "is_one_off_custom": False,
        "is_racing_specific": False,
        "is_amphibious": False,
        "is_military_derived": False,
        "grille_style": "low front grille",
        "headlight_style": "pop-up",
        "taillight_style": "rounded",
        "detected_mods": [],
        "design_guidance": "Mid-engine layout, low nose, large rear wing.",
        "taxonomy_suggestions": [],
    }


@pytest.fixture
def mock_claude_response():
    """Return a valid structured output dict for a simple car design.

    Kept for backward compatibility with older tests that expect a dict.
    """
    return {
        "design_notes": "Test design for a sports car.",
        "total_parts": 50,
        "body_color_id": 4,
        "parts": [
            {
                "part_num": "3024.dat",
                "bricklink_id": "3024",
                "color_id": 4,
                "x": 0, "y": -24, "z": 0,
                "rotation": "1 0 0 0 1 0 0 0 1",
                "quantity": 1,
                "step": 1,
            },
            {
                "part_num": "3005.dat",
                "bricklink_id": "3005",
                "color_id": 0,
                "x": 0, "y": -40, "z": 0,
                "rotation": "1 0 0 0 1 0 0 0 1",
                "quantity": 2,
                "step": 1,
            },
        ],
    }


@pytest.fixture
def sample_lego_set() -> LegoSet:
    """Create a sample LegoSet for testing."""
    return LegoSet(
        set_num="75895-1",
        name="1974 Porsche 911 Turbo 3.0",
        year=2019,
        brick_count=180,
        car_make="Porsche",
        car_model="911 Turbo",
        theme_id=601,
    )


@pytest.fixture
def sample_car() -> Car:
    """Create a sample Car for testing."""
    return Car(
        id=None,
        make="Porsche",
        model="911",
        year=2020,
        body_style="sports_car",
    )


@pytest.fixture
def sample_design(sample_car) -> Design:
    """Create a sample Design for testing."""
    return Design(
        car_id=None,
        match_level=1,
        status="completed",
        matched_set_num="75895-1",
        parts_count=180,
    )


# ── Helper factories ───────────────────────────────────


async def create_test_car(db: AsyncSession, make="Porsche", model="911", year=2020, **kwargs) -> Car:
    """Factory helper: create and flush a Car."""
    car = Car(make=make, model=model, year=year, **kwargs)
    db.add(car)
    await db.flush()
    await db.refresh(car)
    return car


async def create_test_set(db: AsyncSession, set_num="75895-1", **kwargs) -> LegoSet:
    """Factory helper: create and flush a LegoSet."""
    defaults = {
        "name": "Test Set",
        "set_num": set_num,
        "year": 2019,
        "brick_count": 180,
        "car_make": "Porsche",
        "car_model": "911 Turbo",
        "theme_id": 601,
    }
    defaults.update(kwargs)
    lego_set = LegoSet(**defaults)
    db.add(lego_set)
    await db.flush()
    await db.refresh(lego_set)
    return lego_set
