"""Web-based car research service.

When a car model is not in the local database and NHTSA returns nothing
(e.g., Chinese brands, niche manufacturers, custom builds), this service
searches the web to gather high-quality car specifications.

Priority sources:
  1. Official manufacturer website (e.g., porsche.com, toyota.com)
  2. Wikipedia (comprehensive, structured specs)
  3. Automotive databases (caranddriver.com, autoevolution.com, etc.)
  4. Owner forums and reviews

Extracted data feeds into the design pipeline for accurate LEGO generation.
"""

import re
from dataclasses import dataclass, field


@dataclass
class CarResearchResult:
    """Structured car data gathered from web research."""
    make: str
    model: str
    year: int
    body_style: str = ""               # sports_car, suv, sedan, etc.
    dimensions: dict = field(default_factory=dict)
    # {length_mm, width_mm, height_mm, wheelbase_mm}
    colors_available: list[str] = field(default_factory=list)
    engine_type: str = ""              # e.g., "3.0L Twin-Turbo V6"
    drive_type: str = ""               # RWD, AWD, FWD
    distinctive_features: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    official_url: str = ""
    source: str = ""                   # Where the data came from
    confidence: float = 0.0            # 0-1, how reliable the data is
    raw_notes: str = ""                # Unstructured notes from research


class CarResearchService:
    """Searches the web for car specifications, prioritizing official sources.

    This is designed to be called from the matching pipeline when local
    database + NHTSA both fail. It enriches the car data before passing
    to the design generator.
    """

    # Known manufacturer domains (official sites, prioritized)
    OFFICIAL_DOMAINS: dict[str, str] = {
        # Major global brands
        "toyota": "toyota.com", "lexus": "lexus.com",
        "honda": "honda.com", "acura": "acura.com",
        "nissan": "nissan-global.com", "infiniti": "infiniti.com",
        "mazda": "mazda.com",
        "subaru": "subaru.com",
        "mitsubishi": "mitsubishi-motors.com",
        "suzuki": "globalsuzuki.com",
        # European
        "bmw": "bmw.com", "mini": "mini.com", "rolls-royce": "rolls-roycemotorcars.com",
        "mercedes": "mercedes-benz.com", "mercedes-benz": "mercedes-benz.com",
        "audi": "audi.com",
        "porsche": "porsche.com",
        "volkswagen": "volkswagen.com", "vw": "volkswagen.com",
        "volvo": "volvocars.com",
        "jaguar": "jaguar.com", "land rover": "landrover.com",
        "bentley": "bentleymotors.com",
        "lamborghini": "lamborghini.com",
        "ferrari": "ferrari.com",
        "maserati": "maserati.com",
        "alfa romeo": "alfaromeo.com",
        "fiat": "fiat.com",
        "bugatti": "bugatti.com",
        "aston martin": "astonmartin.com",
        "mclaren": "mclaren.com",
        "lotus": "lotuscars.com",
        # American
        "ford": "ford.com", "lincoln": "lincoln.com",
        "chevrolet": "chevrolet.com", "chevy": "chevrolet.com",
        "gmc": "gmc.com", "cadillac": "cadillac.com",
        "dodge": "dodge.com", "ram": "ramtrucks.com",
        "jeep": "jeep.com", "chrysler": "chrysler.com",
        "tesla": "tesla.com",
        # Korean
        "hyundai": "hyundai.com", "kia": "kia.com",
        "genesis": "genesis.com",
        # Chinese brands (global sites)
        "byd": "byd.com", "bydglobal": "bydglobal.com",
        "nio": "nio.com", "nio global": "nio.com",
        "xpeng": "xpeng.com", "x peng": "xpeng.com",
        "li auto": "lixiang.com", "li xiang": "lixiang.com",
        "zeekr": "zeekr.com", "zeekr global": "zeekrglobal.com",
        "great wall": "gwm-global.com", "gwm": "gwm-global.com",
        "haval": "haval-global.com",
        "tank": "tanksuv.com",
        "ora": "oraev.com",
        "lynk & co": "lynkco.com", "lynkco": "lynkco.com",
        "voyah": "voyah.com",
        "hongqi": "hongqi-auto.com",
        "changan": "changan.com.cn",
        "geely": "geely.com",
        "saic": "saicmotor.com",
        "mg": "mg.co.uk",
        "polestar": "polestar.com",
    }

    # High-quality automotive review sites (secondary)
    REVIEW_SITES = [
        "wikipedia.org", "caranddriver.com", "motortrend.com",
        "autocar.co.uk", "evo.co.uk", "topgear.com",
        "autoevolution.com", "ultimatecarpage.com",
        "netcarshow.com", "carscoops.com",
    ]

    @classmethod
    def get_official_domain(cls, make: str) -> str | None:
        """Get the official manufacturer domain for a car make."""
        make_lower = make.lower().strip()
        # Direct match
        if make_lower in cls.OFFICIAL_DOMAINS:
            return cls.OFFICIAL_DOMAINS[make_lower]
        # Partial match
        for key, domain in cls.OFFICIAL_DOMAINS.items():
            if key in make_lower or make_lower in key:
                return domain
        return None

    @classmethod
    def build_search_queries(cls, make: str, model: str, year: int) -> list[dict]:
        """Build prioritized search queries for this car.

        Returns list of {query, priority, purpose} dicts.
        """
        car = f"{year} {make} {model}".strip()
        official_domain = cls.get_official_domain(make)

        queries = []

        # Priority 1: Official manufacturer page
        if official_domain:
            queries.append({
                "query": f"site:{official_domain} {car} specifications",
                "priority": 1,
                "purpose": "official_specs",
                "preferred_domain": official_domain,
            })
            queries.append({
                "query": f"site:{official_domain} {car} dimensions colors",
                "priority": 1,
                "purpose": "official_details",
                "preferred_domain": official_domain,
            })

        # Priority 2: Wikipedia
        queries.append({
            "query": f"{car} wikipedia specifications dimensions",
            "priority": 2,
            "purpose": "wikipedia_specs",
            "preferred_domain": "wikipedia.org",
        })

        # Priority 3: Automotive review sites
        queries.append({
            "query": f"{car} specifications dimensions body style exterior interior",
            "priority": 3,
            "purpose": "detailed_specs",
        })

        # Priority 4: Image search (for visual analysis)
        queries.append({
            "query": f"{car} front side rear view official photo",
            "priority": 4,
            "purpose": "reference_images",
        })

        return queries

    @classmethod
    def parse_specs_from_text(cls, text: str, make: str, model: str) -> dict:
        """Parse car specifications from unstructured text (webpage content).

        Extracts dimensions, body style, engine, etc. using regex patterns.
        """
        result = {
            "body_style": "",
            "length_mm": None,
            "width_mm": None,
            "height_mm": None,
            "wheelbase_mm": None,
            "engine": "",
            "drive_type": "",
            "colors": [],
            "features": [],
        }

        text_lower = text.lower()

        # Body style detection
        body_styles = {
            "suv": ["suv", "sport utility", "crossover"],
            "sedan": ["sedan", "saloon", "4-door"],
            "coupe": ["coupe", "2-door"],
            "hatchback": ["hatchback", "hatch", "5-door"],
            "wagon": ["wagon", "estate", "shooting brake"],
            "pickup": ["pickup", "pick-up", "truck", "double cab"],
            "convertible": ["convertible", "cabriolet", "roadster", "spider", "spyder"],
            "sports_car": ["sports car", "supercar", "hypercar"],
        }
        for style, keywords in body_styles.items():
            if any(kw in text_lower for kw in keywords):
                if not result["body_style"]:
                    result["body_style"] = style

        # Dimensions: Look for patterns like "4,785 mm (188.4 in)" or "Length: 185.6 inches"
        dim_patterns = {
            "length_mm": [
                r'(?:length|overall length)[:\s]*(\d{3,5})\s*(?:mm|millimeters)',
                r'(?:length|overall length)[:\s]*(\d+\.?\d*)\s*(?:in|inches)',
                r'(\d{4})\s*mm\s*(?:length|long)',
            ],
            "width_mm": [
                r'(?:width|overall width)[:\s]*(\d{3,5})\s*(?:mm|millimeters)',
                r'(?:width|overall width)[:\s]*(\d+\.?\d*)\s*(?:in|inches)',
                r'(\d{4})\s*mm\s*(?:width|wide)',
            ],
            "height_mm": [
                r'(?:height|overall height)[:\s]*(\d{3,5})\s*(?:mm|millimeters)',
                r'(?:height|overall height)[:\s]*(\d+\.?\d*)\s*(?:in|inches)',
            ],
            "wheelbase_mm": [
                r'wheelbase[:\s]*(\d{3,5})\s*(?:mm|millimeters)',
                r'wheelbase[:\s]*(\d+\.?\d*)\s*(?:in|inches)',
            ],
        }
        for key, patterns in dim_patterns.items():
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    val = float(m.group(1))
                    # If value is in inches (likely < 250 for car dimensions), convert to mm
                    if "in" in pat or "inches" in pat:
                        if val < 250:
                            val = val * 25.4
                    result[key] = round(val)
                    break

        # Engine type
        engine_pats = [
            r'(\d+\.?\d*\s*(?:L|Liter|litre)\s*(?:twin-?)?(?:turbo|supercharged)?\s*(?:V|I|W|Flat|Inline)[- ]?\d+)',
            r'((?:V|Inline|Flat)[- ]?\d+\s*(?:twin-?)?(?:turbo|supercharged)?\s*\d+\.?\d*\s*(?:L|Liter))',
        ]
        for pat in engine_pats:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result["engine"] = m.group(1).strip()
                break

        # Drive type
        if any(kw in text_lower for kw in ["all-wheel drive", "awd", "4wd", "4x4", "four-wheel"]):
            result["drive_type"] = "AWD"
        elif any(kw in text_lower for kw in ["rear-wheel drive", "rwd", "rear wheel"]):
            result["drive_type"] = "RWD"
        elif any(kw in text_lower for kw in ["front-wheel drive", "fwd", "front wheel"]):
            result["drive_type"] = "FWD"

        # Colors
        color_keywords = [
            "red", "blue", "black", "white", "silver", "gray", "grey", "green",
            "yellow", "orange", "purple", "brown", "gold", "bronze", "copper",
            "matte", "metallic", "pearl", "mica",
        ]
        for color in color_keywords:
            if color in text_lower:
                # Find context around color mention
                idx = text_lower.find(color)
                context = text[max(0, idx - 30):idx + 60]
                if any(kw in context.lower() for kw in ["paint", "color", "available", "exterior", "option"]):
                    if color not in result["colors"]:
                        result["colors"].append(color)

        # Distinctive features
        feature_keywords = [
            "led headlight", "led daytime", "panoramic roof", "sunroof", "moonroof",
            "active aero", "rear spoiler", "diffuser", "side air intake",
            "hood scoop", "fender flare", "wide body", "carbon fiber",
            "split grille", "kidney grille", "spindle grille",
            "pop-up headlight", "projector headlight", "matrix led",
            "dual exhaust", "quad exhaust", "center exhaust",
            "forged wheel", "alloy wheel", "aerodynamic",
        ]
        for feat in feature_keywords:
            if feat in text_lower:
                if feat not in result["features"]:
                    result["features"].append(feat)

        return result

    @classmethod
    def build_research_result(
        cls,
        make: str,
        model: str,
        year: int,
        nhtsa_data: dict | None = None,
        research_data: dict | None = None,
    ) -> CarResearchResult:
        """Build a CarResearchResult from NHTSA + research metadata.

        Used by the design flow to persist basic specs into the CarSpec
        knowledge base even when no full web research is performed.
        """
        nhtsa_data = nhtsa_data or {}
        research_data = research_data or {}
        official_domain = research_data.get("official_domain") or cls.get_official_domain(make)

        return CarResearchResult(
            make=make,
            model=model,
            year=year,
            body_style=nhtsa_data.get("body_style", ""),
            dimensions={
                "length_mm": nhtsa_data.get("length_mm"),
                "width_mm": nhtsa_data.get("width_mm"),
                "height_mm": nhtsa_data.get("height_mm"),
                "wheelbase_mm": nhtsa_data.get("wheelbase_mm"),
            },
            source=official_domain or "nhtsa",
            confidence=0.5 if nhtsa_data.get("validated") else 0.3,
        )

    @classmethod
    def build_research_prompt(
        cls,
        make: str,
        model: str,
        year: int,
        search_results_text: str,
    ) -> str:
        """Build a prompt for Claude to interpret web search results.

        Claude reads the search results and outputs structured car data
        for the LEGO design pipeline.
        """
        return f"""## Web Research Results for {year} {make} {model}

{search_results_text[:8000]}

## Instructions

Extract ALL relevant car specifications from the above search results to create an accurate LEGO Speed Champions model.

Output using the output_car_specs function with:
1. **body_style**: sports_car / suv / sedan / pickup / hatchback / wagon / coupe / convertible
2. **real_dimensions**: length/width/height in mm (if found)
3. **distinctive_design_features**: What makes this car visually unique?
4. **primary_colors**: What factory paint colors are available?
5. **design_guidance**: Specific tips for LEGO modeling — grille shape, headlight style, body proportions, wheel design, special body lines
6. **reference_images_note**: Describe what the car looks like (front grille, side profile, rear) so the LEGO designer can capture its essence even without seeing images"""


@dataclass
class CarSpecs:
    """Structured car specs extracted by Claude from web research."""
    body_style: str = "sports_car"
    real_length_mm: int = 4500
    real_width_mm: int = 1900
    real_height_mm: int = 1300
    distinctive_features: list[str] = field(default_factory=list)
    primary_colors: list[str] = field(default_factory=list)
    design_guidance: str = ""
    reference_description: str = ""
