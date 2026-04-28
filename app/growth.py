"""
Growth chart analyzer using WHO percentile data.

Determines where a child falls on standard growth charts and flags
when measurements are outside normal ranges — a key uncertainty signal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class GrowthAnalyzer:
    """Analyzes child measurements against WHO growth charts."""

    def __init__(self) -> None:
        self._data: dict = {}
        self._load_data()

    def _load_data(self) -> None:
        path = DATA_DIR / "growth_charts.json"
        with open(path, "r", encoding="utf-8") as f:
            self._data = json.load(f)

    def _find_nearest_age_key(self, age_months: int, available_keys: list[str]) -> str:
        """Find the nearest age key in the growth chart data."""
        int_keys = sorted(int(k) for k in available_keys)
        closest = min(int_keys, key=lambda k: abs(k - age_months))
        return str(closest)

    def _determine_percentile_range(
        self, value: float, percentile_data: dict[str, float]
    ) -> str:
        """Determine which percentile range a value falls in."""
        p3 = percentile_data["p3"]
        p15 = percentile_data["p15"]
        p50 = percentile_data["p50"]
        p85 = percentile_data["p85"]
        p97 = percentile_data["p97"]

        if value < p3:
            return "below 3rd"
        elif value < p15:
            return "3rd-15th"
        elif value < p50:
            return "15th-50th"
        elif value < p85:
            return "50th-85th"
        elif value < p97:
            return "85th-97th"
        else:
            return "above 97th"

    def analyze(
        self,
        age_months: int,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
    ) -> dict:
        """
        Analyze a child's measurements against WHO growth charts.
        Uses average of boys/girls data (gender-neutral since input doesn't include gender).
        """
        result = {
            "weight_percentile": None,
            "height_percentile": None,
            "is_weight_typical": True,
            "is_height_typical": True,
            "flags": [],
        }

        # Use boys data as representative (averaged charts would be better
        # but for simplicity we use boys — noted as limitation)
        weight_data = self._data.get("weight_for_age_kg", {}).get("boys", {})
        height_data = self._data.get("height_for_age_cm", {}).get("boys", {})

        if weight_kg is not None and weight_data:
            age_key = self._find_nearest_age_key(age_months, list(weight_data.keys()))
            percentiles = weight_data[age_key]
            pct_range = self._determine_percentile_range(weight_kg, percentiles)
            result["weight_percentile"] = pct_range

            if pct_range in ("below 3rd", "above 97th"):
                result["is_weight_typical"] = False
                result["flags"].append(
                    f"Weight ({weight_kg} kg) is {pct_range} percentile for {age_months} months — "
                    f"this is outside typical range, sizing may be less predictable"
                )
            elif pct_range in ("3rd-15th", "85th-97th"):
                result["flags"].append(
                    f"Weight ({weight_kg} kg) is in the {pct_range} percentile range — "
                    f"consider that standard sizes may not fit perfectly"
                )

        if height_cm is not None and height_data:
            age_key = self._find_nearest_age_key(age_months, list(height_data.keys()))
            percentiles = height_data[age_key]
            pct_range = self._determine_percentile_range(height_cm, percentiles)
            result["height_percentile"] = pct_range

            if pct_range in ("below 3rd", "above 97th"):
                result["is_height_typical"] = False
                result["flags"].append(
                    f"Height ({height_cm} cm) is {pct_range} percentile for {age_months} months — "
                    f"this is outside typical range, sizing may be less predictable"
                )
            elif pct_range in ("3rd-15th", "85th-97th"):
                result["flags"].append(
                    f"Height ({height_cm} cm) is in the {pct_range} percentile range — "
                    f"consider that standard sizes may not fit perfectly"
                )

        return result


# Module-level singleton
_analyzer: Optional[GrowthAnalyzer] = None


def get_analyzer() -> GrowthAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = GrowthAnalyzer()
    return _analyzer
