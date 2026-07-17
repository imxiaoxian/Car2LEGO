"""NHTSA vPIC API client — validates car make/model/year and fetches specifications.

The NHTSA (National Highway Traffic Safety Administration) vPIC API is free,
requires no authentication, and provides vehicle make/model/year validation plus
body style and dimension data.
"""

from app.integrations.base import BaseApiClient

NHTSA_BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"


class NhtsaClient(BaseApiClient):
    def __init__(self):
        super().__init__(base_url=NHTSA_BASE_URL, timeout=15.0)

    async def get_models_for_make_year(self, make: str, year: int) -> list[dict]:
        """Return all models for a given make and model year."""
        try:
            data = await self.get(
                f"/GetModelsForMakeYear/make/{make}/modelyear/{year}",
                params={"format": "json"},
            )
            return data.get("Results", [])
        except Exception:
            return []

    async def validate_car(self, make: str, model: str, year: int) -> dict | None:
        """Check if a car make/model/year combination is valid.

        Returns the best-matching NHTSA record, or None if not found.
        """
        results = await self.get_models_for_make_year(make, year)
        if not results:
            return None

        # Find best match (case-insensitive)
        model_lower = model.lower()
        for r in results:
            if r.get("Model_Name", "").lower() == model_lower:
                return r

        # Fuzzy: partial match
        for r in results:
            if model_lower in r.get("Model_Name", "").lower():
                return r

        return None

    async def get_vehicle_details(self, make: str, model: str, year: int) -> dict:
        """Get full vehicle specifications including body style."""
        result = await self.validate_car(make, model, year)
        if result:
            return {
                "make": result.get("Make_Name", make),
                "model": result.get("Model_Name", model),
                "year": year,
                "body_style": self._classify_body_style(result),
                "validated": True,
            }
        return {
            "make": make,
            "model": model,
            "year": year,
            "body_style": None,
            "validated": False,
        }

    @staticmethod
    def _classify_body_style(nhtsa_record: dict) -> str | None:
        """Map NHTSA vehicle type to our body style categories."""
        vehicle_type = nhtsa_record.get("VehicleType", "").lower() if nhtsa_record else ""
        if "passenger" in vehicle_type:
            return "sedan"
        if "truck" in vehicle_type:
            return "pickup"
        if "multipurpose" in vehicle_type:
            return "suv"
        return None


# Singleton
nhtsa_client = NhtsaClient()
