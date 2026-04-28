"""
RAG-style sizing data retriever.

Loads brand sizing charts from the JSON knowledge base and retrieves
the most relevant sizing information for a given query.
This implements the RAG requirement — retrieving brand-specific data
to ground the recommendation in real sizing info rather than hallucinating.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Resolve data directory relative to this file
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SizingRetriever:
    """Retrieves brand sizing data from local JSON knowledge base."""

    def __init__(self) -> None:
        self._brand_data: dict = {}
        self._generic_data: dict = {}
        self._load_data()

    def _load_data(self) -> None:
        sizing_path = DATA_DIR / "brand_sizing.json"
        with open(sizing_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._brand_data = data.get("brands", {})
        self._generic_data = data.get("generic_sizing", {})

    @property
    def available_brands(self) -> list[str]:
        return list(self._brand_data.keys())

    def find_brand(self, query: str) -> Optional[str]:
        """Fuzzy-match a brand name from user input."""
        if not query:
            return None
        q = query.lower().strip()
        for brand_name in self._brand_data:
            if q == brand_name.lower():
                return brand_name
        # Partial match
        for brand_name in self._brand_data:
            if q in brand_name.lower() or brand_name.lower() in q:
                return brand_name
        # Common aliases
        aliases = {
            "carters": "Carter's",
            "carter": "Carter's",
            "hm": "H&M Kids",
            "h&m": "H&M Kids",
            "zara": "Zara Baby",
            "mothercare": "Mothercare",
            "babyshop": "BabyShop",
            "baby shop": "BabyShop",
        }
        return aliases.get(q)

    def get_brand_info(self, brand: str) -> Optional[dict]:
        """Get full brand info including sizing notes and fit tendency."""
        matched = self.find_brand(brand)
        if matched and matched in self._brand_data:
            return {
                "brand_name": matched,
                **self._brand_data[matched],
            }
        return None

    def get_matching_sizes(
        self,
        age_months: int,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
        brand: Optional[str] = None,
    ) -> dict:
        """
        Retrieve sizes that match the child's measurements.
        Returns brand-specific sizes if brand is found, otherwise generic.

        This is the core RAG retrieval: we pull relevant sizing documents
        based on the child's measurements.
        """
        result = {
            "brand_found": False,
            "brand_name": None,
            "brand_notes": None,
            "brand_runs": None,
            "using_generic": False,
            "matched_sizes": [],
            "age_matches": [],
            "height_matches": [],
            "weight_matches": [],
        }

        # Try brand-specific first
        sizes_to_search = None
        if brand:
            brand_info = self.get_brand_info(brand)
            if brand_info:
                result["brand_found"] = True
                result["brand_name"] = brand_info["brand_name"]
                result["brand_notes"] = brand_info.get("sizing_notes")
                result["brand_runs"] = brand_info.get("runs")
                sizes_to_search = brand_info.get("sizes", [])

        # Fallback to generic
        if sizes_to_search is None:
            result["using_generic"] = True
            sizes_to_search = self._generic_data.get("sizes", [])

        # Match by age
        for s in sizes_to_search:
            age_lo, age_hi = s["age_range_months"]
            if age_lo <= age_months <= age_hi:
                result["age_matches"].append(s)

        # Match by height
        if height_cm is not None:
            for s in sizes_to_search:
                h_lo, h_hi = s["height_range_cm"]
                if h_lo <= height_cm <= h_hi:
                    result["height_matches"].append(s)

        # Match by weight
        if weight_kg is not None:
            for s in sizes_to_search:
                w_lo, w_hi = s["weight_range_kg"]
                if w_lo <= weight_kg <= w_hi:
                    result["weight_matches"].append(s)

        # Compute best overall matches (sizes that appear in multiple match lists)
        all_match_labels = []
        for match_list in [result["age_matches"], result["height_matches"], result["weight_matches"]]:
            all_match_labels.extend([s["label"] for s in match_list])

        # Count how many criteria each size matches
        label_counts: dict[str, int] = {}
        label_data: dict[str, dict] = {}
        for match_list in [result["age_matches"], result["height_matches"], result["weight_matches"]]:
            for s in match_list:
                label = s["label"]
                label_counts[label] = label_counts.get(label, 0) + 1
                label_data[label] = s

        # Compute a fit score for each size: how well centered the child is
        def _fit_score(label: str) -> float:
            """
            Compute how well the child fits in this size.
            Returns 0-1 where 1 = perfectly centered in all dimension ranges.
            """
            s = label_data[label]
            scores = []
            # Age fit
            age_lo, age_hi = s["age_range_months"]
            age_range = age_hi - age_lo if age_hi > age_lo else 1
            age_pos = (age_months - age_lo) / age_range
            scores.append(1.0 - abs(age_pos - 0.5) * 2)  # 1.0 at center, 0.0 at edges

            if height_cm is not None:
                h_lo, h_hi = s["height_range_cm"]
                h_range = h_hi - h_lo if h_hi > h_lo else 1
                h_pos = (height_cm - h_lo) / h_range
                scores.append(1.0 - abs(h_pos - 0.5) * 2)

            if weight_kg is not None:
                w_lo, w_hi = s["weight_range_kg"]
                w_range = w_hi - w_lo if w_hi > w_lo else 1
                w_pos = (weight_kg - w_lo) / w_range
                scores.append(1.0 - abs(w_pos - 0.5) * 2)

            return sum(scores) / len(scores) if scores else 0

        # Sort by: (1) match count, (2) fit score
        # Tie-break: if fit scores are within 0.15 of each other, prefer larger size
        sorted_labels = sorted(
            label_counts.keys(),
            key=lambda x: (
                label_counts[x],
                _fit_score(x),
            ),
            reverse=True,
        )
        result["matched_sizes"] = [
            {**label_data[label], "match_score": label_counts[label]}
            for label in sorted_labels
        ]

        return result


# Module-level singleton
_retriever: Optional[SizingRetriever] = None


def get_retriever() -> SizingRetriever:
    global _retriever
    if _retriever is None:
        _retriever = SizingRetriever()
    return _retriever
