"""Brand-specific signature features library for LEGO car design.

Provides BrandProfile and BrandFeature dataclasses that define iconic
features for 10+ car brands (Ferrari F40 rear wing, BMW kidney grille, etc.).
These are injected into the LLM prompt as reference coordinates so the LLM
can place brand-accurate detail parts at the right positions.

Usage:
    from app.services.brand_features import get_brand_features
    features = get_brand_features("Ferrari", "F40")
    for feat in features:
        print(f"{feat.feature_id}: {feat.part_num} at ({feat.x}, {feat.y}, {feat.z})")
"""

from dataclasses import dataclass, field


@dataclass
class BrandFeature:
    """A single brand-identifying feature with a suggested part placement."""

    feature_id: str
    part_num: str
    color_id: int
    x: float
    y: float
    z: float
    rotation: str
    description: str


@dataclass
class BrandProfile:
    """Color defaults + model-specific signature features for a brand."""

    brand: str
    default_body_color: int
    default_accent_color: int
    features: dict[str, list[BrandFeature]] = field(default_factory=dict)


# ── Brand feature definitions ──

_FERRARI_F40 = [
    BrandFeature("rear_wing", "44675.dat", 0, 0, 112, 20, "1 0 0 0 1 0 0 0 1",
                 "F40 signature elevated rear wing on twin standoffs"),
    BrandFeature("rear_wing_support", "3023.dat", 0, 0, 96, 20, "1 0 0 0 1 0 0 0 1",
                 "Wing support strut"),
    BrandFeature("pop_up_headlight", "4070.dat", 15, 56, 48, 300, "1 0 0 0 1 0 0 0 1",
                 "Pop-up headlight housing (white)"),
    BrandFeature("pop_up_headlight_lens", "6141.dat", 14, 64, 48, 300, "1 0 0 0 1 0 0 0 1",
                 "Pop-up headlight lens (yellow)"),
    BrandFeature("quad_taillight", "6141.dat", 4, 56, 48, 10, "1 0 0 0 1 0 0 0 1",
                 "Quad round taillight (red)"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 0, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual center exhaust tip"),
    BrandFeature("rear_diffuser_fin", "60481.dat", 0, 0, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Rear diffuser fin"),
    BrandFeature("front_grille", "2412b.dat", 0, 0, 48, 310, "1 0 0 0 1 0 0 0 1",
                 "Wide black front grille"),
    BrandFeature("engine_vent", "30236.dat", 0, 0, 88, 120, "1 0 0 0 1 0 0 0 1",
                 "Engine deck vent/louver behind cabin"),
]

_FERRARI_DEFAULT = [
    BrandFeature("rear_wing", "44675.dat", 0, 0, 104, 20, "1 0 0 0 1 0 0 0 1",
                 "Ferrari rear spoiler"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual exhaust tips"),
    BrandFeature("side_mirror", "4085.dat", 0, 60, 56, 160, "1 0 0 0 1 0 0 0 1",
                 "Side mirror"),
    BrandFeature("front_grille", "2412b.dat", 0, 20, 48, 310, "1 0 0 0 1 0 0 0 1",
                 "Front grille"),
]

_LAMBORGHINI_DEFAULT = [
    BrandFeature("low_front_splitter", "3665.dat", 0, 20, 16, 310, "1 0 0 0 1 0 0 0 1",
                 "Low front splitter lip"),
    BrandFeature("side_air_intake", "30236.dat", 0, 60, 48, 100, "1 0 0 0 1 0 0 0 1",
                 "Large side air intake"),
    BrandFeature("y_taillight", "6141.dat", 4, 0, 56, 10, "1 0 0 0 1 0 0 0 1",
                 "Y-shaped taillight cluster"),
    BrandFeature("rear_wing", "3023.dat", 0, 20, 104, 20, "1 0 0 0 1 0 0 0 1",
                 "Fixed rear wing"),
    BrandFeature("quad_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Quad exhaust tips"),
    BrandFeature("hood_vent", "3069b.dat", 0, 20, 88, 260, "1 0 0 0 1 0 0 0 1",
                 "Hood vent detail"),
]

_PORSCHE_911 = [
    BrandFeature("round_headlight", "6141.dat", 15, 0, 64, 300, "1 0 0 0 1 0 0 0 1",
                 "Porsche 911 signature round headlight"),
    BrandFeature("sloped_rear_window", "30363.dat", 4, 0, 104, 40, "1 0 0 0 1 0 0 0 1",
                 "911 iconic sloped rear window"),
    BrandFeature("integrated_taillight", "2431.dat", 4, 0, 56, 10, "1 0 0 0 1 0 0 0 1",
                 "Integrated taillight bar"),
    BrandFeature("rear_engine_grille", "2412b.dat", 0, 20, 88, 60, "1 0 0 0 1 0 0 0 1",
                 "Rear engine cover grille"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual exhaust tips"),
]

_PORSCHE_DEFAULT = [
    BrandFeature("round_headlight", "6141.dat", 15, 0, 64, 300, "1 0 0 0 1 0 0 0 1",
                 "Porsche round headlight"),
    BrandFeature("rear_spoiler", "3023.dat", 0, 20, 104, 20, "1 0 0 0 1 0 0 0 1",
                 "Deployable rear spoiler"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual exhaust tips"),
]

_MCLAREN_DEFAULT = [
    BrandFeature("large_rear_wing", "44675.dat", 0, 0, 112, 20, "1 0 0 0 1 0 0 0 1",
                 "McLaren large rear wing"),
    BrandFeature("snorkel_intake", "4070.dat", 0, 0, 88, 160, "1 0 0 0 1 0 0 0 1",
                 "McLaren P1-style roof snorkel intake"),
    BrandFeature("led_drl", "3070b.dat", 15, 0, 56, 310, "1 0 0 0 1 0 0 0 1",
                 "LED daytime running light strip"),
    BrandFeature("diffuser_fins", "60481.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Rear diffuser fins"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 20, "1 0 0 0 1 0 0 0 1",
                 "High-mount dual exhaust"),
]

_BUGATTI_DEFAULT = [
    BrandFeature("horseshoe_grille", "2412b.dat", 0, 0, 48, 310, "1 0 0 0 1 0 0 0 1",
                 "Bugatti signature horseshoe front grille"),
    BrandFeature("c_line_side", "3069b.dat", 0, 60, 72, 140, "1 0 0 0 1 0 0 0 1",
                 "Bugatti C-line side detail"),
    BrandFeature("center_exhaust", "4599.dat", 0, 0, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Center exhaust"),
    BrandFeature("rear_wing", "3023.dat", 0, 20, 104, 20, "1 0 0 0 1 0 0 0 1",
                 "Active rear wing"),
]

_KOENIGSEGG_DEFAULT = [
    BrandFeature("large_rear_wing", "44675.dat", 0, 0, 112, 20, "1 0 0 0 1 0 0 0 1",
                 "Koenigsegg large rear wing"),
    BrandFeature("tri_exhaust", "4599.dat", 0, 0, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Center tri-exhaust"),
    BrandFeature("side_air_intake", "30236.dat", 0, 60, 48, 100, "1 0 0 0 1 0 0 0 1",
                 "Large side air intake"),
    BrandFeature("front_splitter", "3665.dat", 0, 20, 16, 310, "1 0 0 0 1 0 0 0 1",
                 "Front splitter"),
]

_PAGANI_DEFAULT = [
    BrandFeature("quad_exhaust", "4599.dat", 0, 0, 88, 20, "1 0 0 0 1 0 0 0 1",
                 "Pagani center quad exhaust (signature)"),
    BrandFeature("large_rear_wing", "44675.dat", 0, 0, 112, 20, "1 0 0 0 1 0 0 0 1",
                 "Large rear wing"),
    BrandFeature("side_air_intake", "30236.dat", 0, 60, 48, 100, "1 0 0 0 1 0 0 0 1",
                 "Side air intake"),
    BrandFeature("front_splitter", "3665.dat", 0, 20, 16, 310, "1 0 0 0 1 0 0 0 1",
                 "Front splitter"),
]

_BMW_DEFAULT = [
    BrandFeature("kidney_grille", "2412b.dat", 0, 0, 56, 310, "1 0 0 0 1 0 0 0 1",
                 "BMW signature kidney grille (two vertical sections)"),
    BrandFeature("kidney_grille_left", "2412b.dat", 0, 20, 56, 310, "1 0 0 0 1 0 0 0 1",
                 "BMW kidney grille right section"),
    BrandFeature("angel_eye_headlight", "6141.dat", 15, 0, 64, 300, "1 0 0 0 1 0 0 0 1",
                 "BMW angel eye halo headlight"),
    BrandFeature("hofmeister_kink", "3069b.dat", 0, 60, 88, 180, "1 0 0 0 1 0 0 0 1",
                 "BMW Hofmeister kink (C-pillar detail)"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual exhaust tips"),
]

_MERCEDES_DEFAULT = [
    BrandFeature("single_bar_grille", "2412b.dat", 0, 0, 56, 310, "1 0 0 0 1 0 0 0 1",
                 "Mercedes single-bar diamond grille"),
    BrandFeature("star_emblem", "6141.dat", 0, 0, 64, 310, "1 0 0 0 1 0 0 0 1",
                 "Three-pointed star emblem (front)"),
    BrandFeature("led_taillight", "2431.dat", 4, 0, 56, 10, "1 0 0 0 1 0 0 0 1",
                 "Mercedes star-shaped LED taillight bar"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual exhaust tips"),
    BrandFeature("side_mirror", "4085.dat", 0, 60, 56, 160, "1 0 0 0 1 0 0 0 1",
                 "Side mirror with turn signal"),
]

_AUDI_DEFAULT = [
    BrandFeature("single_frame_grille", "2412b.dat", 0, 0, 56, 310, "1 0 0 0 1 0 0 0 1",
                 "Audi signature single-frame grille"),
    BrandFeature("led_drl", "3070b.dat", 15, 0, 56, 300, "1 0 0 0 1 0 0 0 1",
                 "Audi LED daytime running light strip"),
    BrandFeature("rings_emblem", "6141.dat", 0, 0, 64, 310, "1 0 0 0 1 0 0 0 1",
                 "Four rings emblem"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual exhaust tips"),
]

_NISSAN_GTR = [
    BrandFeature("quad_round_taillight", "6141.dat", 4, 0, 56, 10, "1 0 0 0 1 0 0 0 1",
                 "GT-R signature four round taillights"),
    BrandFeature("quad_round_taillight_2", "6141.dat", 0, 20, 56, 10, "1 0 0 0 1 0 0 0 1",
                 "GT-R second taillight"),
    BrandFeature("large_rear_wing", "44675.dat", 0, 0, 104, 20, "1 0 0 0 1 0 0 0 1",
                 "GT-R large rear wing"),
    BrandFeature("front_grille", "2412b.dat", 0, 0, 48, 310, "1 0 0 0 1 0 0 0 1",
                 "GT-R front grille"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual exhaust tips"),
]

_TOYOTA_SUPRA = [
    BrandFeature("long_hood_scoop", "30236.dat", 0, 20, 88, 260, "1 0 0 0 1 0 0 0 1",
                 "Supra signature long hood intake"),
    BrandFeature("large_rear_wing", "44675.dat", 0, 0, 104, 20, "1 0 0 0 1 0 0 0 1",
                 "Supra large rear wing"),
    BrandFeature("dual_exhaust", "4599.dat", 0, 20, 24, 10, "1 0 0 0 1 0 0 0 1",
                 "Dual exhaust tips"),
    BrandFeature("front_splitter", "3665.dat", 0, 20, 16, 310, "1 0 0 0 1 0 0 0 1",
                 "Front splitter"),
]

# ── Brand registry ──

BRAND_PROFILES: dict[str, BrandProfile] = {
    "Ferrari": BrandProfile(
        brand="Ferrari",
        default_body_color=4,  # Red
        default_accent_color=0,  # Black
        features={
            "F40": _FERRARI_F40,
            "default": _FERRARI_DEFAULT,
        },
    ),
    "Lamborghini": BrandProfile(
        brand="Lamborghini",
        default_body_color=14,  # Yellow (also 27 Lime for some models)
        default_accent_color=0,
        features={"default": _LAMBORGHINI_DEFAULT},
    ),
    "Porsche": BrandProfile(
        brand="Porsche",
        default_body_color=15,  # White
        default_accent_color=4,  # Red accent
        features={
            "911": _PORSCHE_911,
            "default": _PORSCHE_DEFAULT,
        },
    ),
    "McLaren": BrandProfile(
        brand="McLaren",
        default_body_color=25,  # Orange (McLaren papaya)
        default_accent_color=0,
        features={"default": _MCLAREN_DEFAULT},
    ),
    "Bugatti": BrandProfile(
        brand="Bugatti",
        default_body_color=1,  # Blue
        default_accent_color=89,  # Dark Blue two-tone
        features={"default": _BUGATTI_DEFAULT},
    ),
    "Koenigsegg": BrandProfile(
        brand="Koenigsegg",
        default_body_color=0,  # Black
        default_accent_color=15,  # White accent
        features={"default": _KOENIGSEGG_DEFAULT},
    ),
    "Pagani": BrandProfile(
        brand="Pagani",
        default_body_color=72,  # Dark Gray (carbon)
        default_accent_color=15,  # White
        features={"default": _PAGANI_DEFAULT},
    ),
    "BMW": BrandProfile(
        brand="BMW",
        default_body_color=1,  # Blue
        default_accent_color=0,  # Black
        features={"default": _BMW_DEFAULT},
    ),
    "Mercedes-Benz": BrandProfile(
        brand="Mercedes-Benz",
        default_body_color=71,  # Silver
        default_accent_color=0,  # Black
        features={"default": _MERCEDES_DEFAULT},
    ),
    "Mercedes": BrandProfile(
        brand="Mercedes",
        default_body_color=71,
        default_accent_color=0,
        features={"default": _MERCEDES_DEFAULT},
    ),
    "Audi": BrandProfile(
        brand="Audi",
        default_body_color=15,  # White
        default_accent_color=0,
        features={"default": _AUDI_DEFAULT},
    ),
    "Nissan": BrandProfile(
        brand="Nissan",
        default_body_color=4,  # Red
        default_accent_color=15,
        features={
            "GT-R": _NISSAN_GTR,
            "GTR": _NISSAN_GTR,
            "default": _NISSAN_GTR,
        },
    ),
    "Toyota": BrandProfile(
        brand="Toyota",
        default_body_color=4,  # Red
        default_accent_color=15,
        features={
            "Supra": _TOYOTA_SUPRA,
            "default": _TOYOTA_SUPRA,
        },
    ),
}


def get_brand_features(make: str, model: str) -> list[BrandFeature]:
    """Return brand-specific features for the given car.

    Looks up the brand profile by make, then tries model-specific features
    first, falling back to the brand's "default" features. Returns an empty
    list for unknown brands.
    """
    profile = _find_brand_profile(make)
    if not profile:
        return []

    model_key = _find_model_key(profile, model)
    return profile.features.get(model_key, profile.features.get("default", []))


def get_brand_profile(make: str) -> BrandProfile | None:
    """Return the BrandProfile for a make, or None if unknown."""
    return _find_brand_profile(make)


def _find_brand_profile(make: str) -> BrandProfile | None:
    """Find a brand profile by make name (case-insensitive, partial match)."""
    make_lower = make.lower().strip()
    for brand_key, profile in BRAND_PROFILES.items():
        if brand_key.lower() in make_lower or make_lower in brand_key.lower():
            return profile
    return None


def _find_model_key(profile: BrandProfile, model: str) -> str:
    """Find the best matching model key in a brand's features dict."""
    model_lower = model.lower().strip()
    for key in profile.features:
        if key == "default":
            continue
        if key.lower() in model_lower or model_lower in key.lower():
            return key
    return "default"
