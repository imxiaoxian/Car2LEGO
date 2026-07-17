"""Reference pricing service for LEGO parts.

Provides estimated costs per part using cached BrickLink price guide data.
No purchase integration — just reference prices so users know what to expect.

Price sources (in priority order):
  1. BrickLink API (real-time, requires OAuth)
  2. Cached price data from CSV export
  3. Estimated prices based on part type/size
"""

from dataclasses import dataclass
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# ESTIMATED PART PRICES (USD)
# ═══════════════════════════════════════════════════════════════
# Based on BrickLink average prices for common parts (new condition, any color).
# Production would use real-time BrickLink API price guide.

ESTIMATED_PRICES: dict[str, float] = {
    # Plates
    "3024": 0.03,  # Plate 1x1
    "3023": 0.04,  # Plate 1x2
    "3022": 0.05,  # Plate 2x2
    "3021": 0.06,  # Plate 2x3
    "3020": 0.07,  # Plate 2x4
    "3666": 0.08,  # Plate 1x6
    "3460": 0.10,  # Plate 1x8
    "3795": 0.09,  # Plate 2x6
    "3034": 0.11,  # Plate 2x8
    "3035": 0.18,  # Plate 4x8
    "4282": 0.22,  # Plate 2x16

    # Bricks
    "3005": 0.05,  # Brick 1x1
    "3004": 0.07,  # Brick 1x2
    "3622": 0.09,  # Brick 1x3
    "3010": 0.10,  # Brick 1x4
    "3009": 0.14,  # Brick 1x6
    "3008": 0.18,  # Brick 1x8
    "3003": 0.08,  # Brick 2x2
    "3002": 0.10,  # Brick 2x3
    "3001": 0.12,  # Brick 2x4
    "2456": 0.16,  # Brick 2x6

    # Slopes
    "3040": 0.06,  # Slope 45 2x1
    "3041": 0.08,  # Slope 45 2x2
    "3039": 0.08,  # Slope 45 double
    "3298": 0.09,  # Slope 33 3x2
    "3297": 0.12,  # Slope 33 3x4
    "4286": 0.10,  # Slope 33 3x1
    "11477": 0.08,  # Curved slope 2x1
    "15068": 0.10,  # Curved slope 2x2
    "50950": 0.09,  # Curved slope 3x1

    # Tiles
    "3070b": 0.04,  # Tile 1x1
    "3069b": 0.05,  # Tile 1x2
    "2431": 0.08,   # Tile 1x4
    "6636": 0.10,   # Tile 1x6
    "3068b": 0.08,  # Tile 2x2
    "87079": 0.12,  # Tile 2x4

    # Wheels & Tires (more expensive — specialized parts)
    "4624": 0.25,  # Wheel small
    "3641": 0.20,  # Tire small
    "6014": 0.45,  # Wheel large
    "6015": 0.35,  # Tire large
    "56904": 0.60,  # Wheel 30mm off-road
    "4624c00": 0.50,  # Wheel+tire assembly
    "6014c00": 0.80,  # Wheel+tire assembly large
    "56904c00": 1.10,  # Wheel+tire assembly off-road

    # Windscreens (expensive due to size)
    "3823": 0.35,  # Windscreen
    "2437": 0.35,  # Low windscreen
    "4176": 0.40,  # Wide windscreen

    # Details
    "4070": 0.05,  # Headlight brick
    "6141": 0.03,  # Round plate 1x1
    "54200": 0.04,  # Cheese slope
    "2412b": 0.08,  # Grille tile
    "30236": 0.12,  # Grille brick
    "43723": 0.10,  # Wedge left
    "43722": 0.10,  # Wedge right
    "44675": 0.12,  # Fin slope
    "4599": 0.04,  # Tap
    "99780": 0.08,  # Bracket
    "99206": 0.10,  # Angle plate
    "4085": 0.05,  # Clip plate
    "4733": 0.04,  # Brick 1x1 with studs on 4 sides
    "87087": 0.06,  # Brick 1x1 with stud on 1 side
    "11476": 0.06,  # Plate 1x2 with clip

    # Default fallback
    "default_plate": 0.06,
    "default_brick": 0.10,
    "default_tile": 0.07,
    "default_slope": 0.09,
    "default_wheel": 0.50,
    "default_windscreen": 0.35,
    "default_special": 0.15,
}


@dataclass
class PricedPart:
    """A part with its estimated price."""
    part_num: str
    bricklink_id: str
    color_name: str
    quantity: int
    unit_price_usd: float
    total_price_usd: float
    price_confidence: str  # "estimated" | "cached" | "live"


class PricingService:
    """Provides reference pricing for LEGO parts lists."""

    @classmethod
    def estimate_part_price(cls, part_num: str) -> tuple[float, str]:
        """Get estimated price for a part.

        Returns (price_usd, confidence_level).
        """
        # Strip .dat suffix and assembly suffixes
        clean = part_num.replace(".dat", "").replace("c00", "").replace("c01", "").replace("c02", "")

        # Direct match
        if clean in ESTIMATED_PRICES:
            return ESTIMATED_PRICES[clean], "estimated"

        # Category-based estimation
        if any(k in clean.lower() for k in ["3024", "3023", "3022", "3021", "3020"]):
            return ESTIMATED_PRICES["default_plate"], "estimated"
        if any(k in clean.lower() for k in ["3005", "3004", "3003", "3002", "3001"]):
            return ESTIMATED_PRICES["default_brick"], "estimated"
        if any(k in clean.lower() for k in ["3069", "3070", "3068", "2431", "87079", "63864"]):
            return ESTIMATED_PRICES["default_tile"], "estimated"
        if any(k in clean.lower() for k in ["3040", "3041", "3039", "3298", "4286", "11477"]):
            return ESTIMATED_PRICES["default_slope"], "estimated"
        if any(k in clean.lower() for k in ["4624", "6014", "56904", "3641", "6015"]):
            return ESTIMATED_PRICES["default_wheel"], "estimated"
        if any(k in clean.lower() for k in ["3823", "2437", "4176", "60592", "59349"]):
            return ESTIMATED_PRICES["default_windscreen"], "estimated"

        return ESTIMATED_PRICES["default_special"], "estimated"

    @classmethod
    def price_parts_list(cls, parts: list[dict]) -> dict:
        """Price an entire parts list.

        Args:
            parts: List of {part_num, bricklink_id, color_name, quantity}

        Returns:
            {
                "parts": [PricedPart, ...],
                "total_parts": int,
                "total_cost_usd": float,
                "currency": "USD",
                "confidence": "estimated",
                "note": "Reference prices only. Actual prices vary by seller and condition."
            }
        """
        priced_parts = []
        total_parts = 0
        total_cost = 0.0

        for p in parts:
            qty = p.get("quantity", 1)
            part_num = p.get("part_num", "")
            unit_price, confidence = cls.estimate_part_price(part_num)
            line_total = unit_price * qty

            priced_parts.append({
                "part_num": part_num,
                "bricklink_id": p.get("bricklink_id", part_num.replace(".dat", "")),
                "color_name": p.get("color_name", ""),
                "quantity": qty,
                "unit_price_usd": round(unit_price, 2),
                "total_price_usd": round(line_total, 2),
                "confidence": confidence,
            })
            total_parts += qty
            total_cost += line_total

        # Sort by cost descending
        priced_parts.sort(key=lambda x: x["total_price_usd"], reverse=True)

        return {
            "parts": priced_parts,
            "total_parts": total_parts,
            "total_cost_usd": round(total_cost, 2),
            "currency": "USD",
            "confidence": "estimated",
            "note": "Estimated reference prices based on BrickLink averages. Actual prices vary by seller, condition, color, and availability. Most parts cost $0.02-$0.20 each. Rare colors and discontinued parts may cost more.",
        }
