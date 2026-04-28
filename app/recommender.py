"""
Core size recommendation engine.

Combines:
1. RAG retrieval (brand sizing data)
2. Growth chart analysis (WHO percentiles)
3. Rule-based logic (deterministic sizing)
4. LLM enhancement (optional, for richer reasoning)

The engine always produces a valid rule-based recommendation first,
then optionally enhances it with an LLM for more natural language.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

from .growth import get_analyzer
from .models import (
    AlternativeSizes,
    Confidence,
    GrowthPercentile,
    Language,
    SizeRecommendation,
    SizeRequest,
    UncertaintyFlag,
)
from .retriever import get_retriever
from . import i18n

load_dotenv()
logger = logging.getLogger(__name__)


class SizeRecommender:
    """
    The main recommendation engine. Implements an agent-like pattern:
    1. RETRIEVE relevant sizing data (RAG)
    2. ANALYZE growth percentiles
    3. REASON about the best size (rules)
    4. ENHANCE with LLM (optional)
    5. VALIDATE output (Pydantic)
    """

    def __init__(self) -> None:
        self.retriever = get_retriever()
        self.growth_analyzer = get_analyzer()
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat-v3-0324")
        self.llm_available = bool(self.api_key) and self.api_key != "your_key_here"

    async def recommend(self, request: SizeRequest) -> SizeRecommendation:
        """
        Main entry point. Produces a size recommendation.

        Pipeline:
        1. Retrieve brand sizing data
        2. Analyze growth chart percentiles
        3. Apply rule-based logic to select size
        4. (Optional) Enhance reasoning with LLM
        5. Validate and return structured output
        """
        # Step 1: RAG retrieval
        sizing_data = self.retriever.get_matching_sizes(
            age_months=request.age_months,
            height_cm=request.height_cm,
            weight_kg=request.weight_kg,
            brand=request.brand,
        )

        # Step 2: Growth analysis
        growth_info = self.growth_analyzer.analyze(
            age_months=request.age_months,
            height_cm=request.height_cm,
            weight_kg=request.weight_kg,
        )

        # Step 3: Rule-based recommendation
        recommendation = self._rule_based_recommend(request, sizing_data, growth_info)

        # Step 4: Optional LLM enhancement
        if self.llm_available:
            try:
                recommendation = await self._llm_enhance(
                    request, sizing_data, growth_info, recommendation
                )
            except Exception as e:
                logger.warning(f"LLM enhancement failed, using rule-based: {e}")
                recommendation.uncertainties.append(
                    UncertaintyFlag(
                        flag="LLM unavailable",
                        detail="Could not enhance with AI reasoning -- using rule-based recommendation only",
                    )
                )

        # Step 5: Localize to Arabic if requested
        if request.lang == Language.AR:
            recommendation = self._localize_ar(recommendation, request)

        return recommendation

    def _rule_based_recommend(
        self,
        request: SizeRequest,
        sizing_data: dict,
        growth_info: dict,
    ) -> SizeRecommendation:
        """
        Deterministic rule-based recommendation.
        This is the backbone — always produces a valid result even without LLM.
        """
        uncertainties: list[UncertaintyFlag] = []
        what_to_verify: list[str] = []
        confidence = Confidence.HIGH

        # --- Determine recommended size ---
        matched = sizing_data.get("matched_sizes", [])
        age_matches = sizing_data.get("age_matches", [])

        recommended_label = None
        reasoning_parts: list[str] = []

        if matched:
            # Best match: size that matches the most criteria
            best = matched[0]
            recommended_label = best["label"]
            match_score = best.get("match_score", 1)
            total_criteria = sum([
                1,  # age always counted
                1 if request.height_cm else 0,
                1 if request.weight_kg else 0,
            ])
            reasoning_parts.append(
                f"Size '{recommended_label}' matches {match_score}/{total_criteria} "
                f"of the provided measurements."
            )

            if match_score == total_criteria and total_criteria >= 2:
                # All provided criteria agree on this size -- HIGH confidence
                confidence = Confidence.HIGH
            elif total_criteria == 1:
                # Only age was provided -- we can match, but with reduced confidence
                confidence = Confidence.MEDIUM
                uncertainties.append(UncertaintyFlag(
                    flag="Limited measurements",
                    detail="Only age was provided. Height and weight help narrow down the best size.",
                ))
                what_to_verify.append("Provide height and weight for a more accurate recommendation")
            elif match_score < total_criteria:
                confidence = Confidence.MEDIUM
                what_to_verify.append(
                    "Not all measurements align with this size -- check the size chart"
                )
                # Check if height/weight suggest a DIFFERENT size than age
                height_sizes = {s["label"] for s in sizing_data.get("height_matches", [])}
                weight_sizes = {s["label"] for s in sizing_data.get("weight_matches", [])}
                age_sizes = {s["label"] for s in sizing_data.get("age_matches", [])}
                # If height+weight agree on a size but age doesn't, prefer height+weight
                if height_sizes and weight_sizes:
                    hw_overlap = height_sizes & weight_sizes
                    if hw_overlap and not hw_overlap & age_sizes:
                        # Measurements disagree with age -- use measurement-based size
                        recommended_label = list(hw_overlap)[0]
                        reasoning_parts.append(
                            f"Height and weight both suggest '{recommended_label}', "
                            f"which differs from age-based sizing. Using measurement-based size."
                        )
        elif age_matches:
            recommended_label = age_matches[0]["label"]
            reasoning_parts.append(
                f"Based on age ({request.age_months} months), "
                f"size '{recommended_label}' is the closest match."
            )
            if not request.height_cm and not request.weight_kg:
                confidence = Confidence.MEDIUM
                uncertainties.append(UncertaintyFlag(
                    flag="Limited measurements",
                    detail="Only age was provided. Height and weight help narrow down the best size.",
                ))
                what_to_verify.append("Provide height and weight for a more accurate recommendation")
        else:
            # No matches at all — fallback
            recommended_label = self._age_to_generic_label(request.age_months)
            confidence = Confidence.LOW
            reasoning_parts.append(
                f"No exact size match found for the given measurements. "
                f"Using general age-based sizing: '{recommended_label}'."
            )
            uncertainties.append(UncertaintyFlag(
                flag="No exact match",
                detail="The provided measurements don't fall within standard size ranges. "
                       "This could mean the child is between sizes or the data is unusual.",
            ))
            what_to_verify.append("Consult the brand's size chart directly")

        # --- Brand info ---
        brand_notes = None
        if sizing_data.get("brand_found"):
            brand_name = sizing_data["brand_name"]
            brand_runs = sizing_data.get("brand_runs", "true_to_size")
            brand_sizing_notes = sizing_data.get("brand_notes", "")
            reasoning_parts.append(f"Using {brand_name} size chart ({sizing_data.get('brand_notes', '')}).")

            if brand_runs == "small":
                brand_notes = f"{brand_name} tends to run small — consider sizing up."
                what_to_verify.append(f"{brand_name} runs small, verify with their chart")
            elif brand_runs == "large":
                brand_notes = f"{brand_name} tends to run large — your child might fit the labeled size or one down."
                what_to_verify.append(f"{brand_name} runs large, your child might fit smaller")
        elif request.brand:
            uncertainties.append(UncertaintyFlag(
                flag="Brand not found",
                detail=f"I don't have sizing data for '{request.brand}' — using general size ranges. "
                       f"Available brands: {', '.join(self.retriever.available_brands)}",
            ))
            confidence = Confidence.MEDIUM if confidence == Confidence.HIGH else confidence
            what_to_verify.append(f"Check {request.brand}'s specific size chart")

        if sizing_data.get("using_generic") and not request.brand:
            reasoning_parts.append("Using WHO-based generic sizing (no specific brand requested).")

        # --- Growth chart flags ---
        growth_percentile = None
        if growth_info.get("weight_percentile") or growth_info.get("height_percentile"):
            growth_percentile = GrowthPercentile(
                weight_percentile=growth_info.get("weight_percentile"),
                height_percentile=growth_info.get("height_percentile"),
            )

        if not growth_info.get("is_weight_typical", True):
            confidence = Confidence.LOW
            uncertainties.append(UncertaintyFlag(
                flag="Atypical weight",
                detail=growth_info["flags"][0] if growth_info["flags"] else "Weight outside normal range",
            ))

        if not growth_info.get("is_height_typical", True):
            confidence = Confidence.LOW
            uncertainties.append(UncertaintyFlag(
                flag="Atypical height",
                detail=[f for f in growth_info["flags"] if "Height" in f][0]
                if any("Height" in f for f in growth_info["flags"])
                else "Height outside normal range",
            ))

        for flag in growth_info.get("flags", []):
            if flag not in [u.detail for u in uncertainties]:
                what_to_verify.append(flag)

        # --- Between sizes logic ---
        between_sizes_note = None
        if len(matched) >= 2:
            # Check if the top two matches have DIFFERENT labels
            top_labels = list(dict.fromkeys([m["label"] for m in matched[:3]]))
            if len(top_labels) >= 2:
                sizes_str = " or ".join(top_labels[:2])
                between_sizes_note = f"Child is between {sizes_str} -- size up for room to grow."
                if confidence == Confidence.HIGH:
                    confidence = Confidence.MEDIUM

        # --- Alternative sizes ---
        alt_sizes = AlternativeSizes(
            if_between_sizes=between_sizes_note or (
                "When in doubt, size up for room to grow" if confidence != Confidence.HIGH else None
            ),
            for_brands=brand_notes,
        )

        reasoning = " ".join(reasoning_parts)

        return SizeRecommendation(
            recommended_size=recommended_label or "Unknown",
            confidence=confidence,
            reasoning=reasoning,
            what_to_verify=what_to_verify,
            alternative_sizes=alt_sizes,
            growth_percentile=growth_percentile,
            uncertainties=uncertainties,
            data_source="rule_engine",
        )

    def _age_to_generic_label(self, age_months: int) -> str:
        """Fallback: map age to a generic size label."""
        if age_months <= 1:
            return "Newborn"
        elif age_months <= 3:
            return "0-3 months"
        elif age_months <= 6:
            return "3-6 months"
        elif age_months <= 9:
            return "6-9 months"
        elif age_months <= 12:
            return "9-12 months"
        elif age_months <= 18:
            return "12-18 months"
        elif age_months <= 24:
            return "18-24 months"
        elif age_months <= 36:
            return "2-3 years"
        elif age_months <= 48:
            return "3-4 years"
        elif age_months <= 60:
            return "4-5 years"
        else:
            return "5+ years"

    def _localize_ar(
        self,
        rec: SizeRecommendation,
        request: SizeRequest,
    ) -> SizeRecommendation:
        """
        Translate the recommendation output to Arabic.
        Uses native Arabic copy from the i18n module, NOT machine translation.
        """
        ar = rec.model_copy()

        # Size label
        ar.recommended_size = i18n.SIZE_LABELS_AR.get(
            rec.recommended_size, rec.recommended_size
        )

        # Reasoning — rebuild in Arabic from components
        # We keep a simple approach: translate known patterns, keep rest as-is
        ar_reasoning_parts = []
        for part in rec.reasoning.split(". "):
            part = part.strip().rstrip(".")
            if not part:
                continue
            # Try to match known patterns
            if "matches" in part and "/" in part:
                ar_reasoning_parts.append(
                    i18n.reasoning_size_match_ar(
                        ar.recommended_size,
                        int(part.split("matches ")[1].split("/")[0]),
                        int(part.split("/")[1].split(" ")[0]),
                    )
                )
            elif "Based on age" in part:
                ar_reasoning_parts.append(
                    i18n.reasoning_age_based_ar(request.age_months, ar.recommended_size)
                )
            elif "No exact size match" in part:
                ar_reasoning_parts.append(
                    i18n.reasoning_no_match_ar(ar.recommended_size)
                )
            elif "Using" in part and "size chart" in part:
                brand = request.brand or ""
                ar_reasoning_parts.append(
                    i18n.reasoning_brand_chart_ar(brand, part.split("(")[-1].rstrip(")") if "(" in part else "")
                )
            elif "WHO-based generic" in part:
                ar_reasoning_parts.append(i18n.reasoning_generic_ar())
            elif "Height and weight both suggest" in part:
                label = part.split("'")[1] if "'" in part else ar.recommended_size
                ar_label = i18n.SIZE_LABELS_AR.get(label, label)
                ar_reasoning_parts.append(i18n.reasoning_hw_override_ar(ar_label))
            else:
                ar_reasoning_parts.append(part)
        ar.reasoning = " ".join(ar_reasoning_parts)

        # What to verify
        ar.what_to_verify = []
        for item in rec.what_to_verify:
            if item in i18n.VERIFY_AR:
                ar.what_to_verify.append(i18n.VERIFY_AR[item])
            elif "runs small" in item:
                ar.what_to_verify.append(i18n.brand_runs_small_verify_ar(request.brand or ""))
            elif "runs large" in item:
                ar.what_to_verify.append(i18n.brand_runs_large_verify_ar(request.brand or ""))
            elif "Check " in item and "size chart" in item:
                ar.what_to_verify.append(i18n.check_brand_chart_ar(request.brand or ""))
            else:
                ar.what_to_verify.append(item)

        # Uncertainties
        ar_uncertainties = []
        for u in rec.uncertainties:
            ar_u = i18n.UNCERTAINTY_AR.get(u.flag, {})
            flag = ar_u.get("flag", u.flag)
            if u.flag == "Brand not found":
                detail = i18n.brand_not_found_detail_ar(
                    request.brand or "", self.retriever.available_brands
                )
            elif u.flag == "Atypical weight" and request.weight_kg:
                detail = i18n.atypical_weight_detail_ar(
                    request.weight_kg,
                    rec.growth_percentile.weight_percentile if rec.growth_percentile else "",
                    request.age_months,
                )
            elif u.flag == "Atypical height" and request.height_cm:
                detail = i18n.atypical_height_detail_ar(
                    request.height_cm,
                    rec.growth_percentile.height_percentile if rec.growth_percentile else "",
                    request.age_months,
                )
            else:
                detail = ar_u.get("detail", u.detail)
            ar_uncertainties.append(UncertaintyFlag(flag=flag, detail=detail))
        ar.uncertainties = ar_uncertainties

        # Alternative sizes
        if rec.alternative_sizes.if_between_sizes:
            if "between" in rec.alternative_sizes.if_between_sizes.lower():
                ar.alternative_sizes = AlternativeSizes(
                    if_between_sizes=i18n.between_sizes_ar(
                        rec.alternative_sizes.if_between_sizes.split("between ")[1].split(" --")[0]
                        if "between " in rec.alternative_sizes.if_between_sizes else ""
                    ),
                    for_brands=rec.alternative_sizes.for_brands,
                )
            elif "doubt" in rec.alternative_sizes.if_between_sizes.lower():
                ar.alternative_sizes = AlternativeSizes(
                    if_between_sizes=i18n.when_in_doubt_ar(),
                    for_brands=rec.alternative_sizes.for_brands,
                )

        if rec.alternative_sizes.for_brands:
            if "small" in rec.alternative_sizes.for_brands.lower():
                ar.alternative_sizes.for_brands = i18n.brand_runs_small_tip_ar(request.brand or "")
            elif "large" in rec.alternative_sizes.for_brands.lower():
                ar.alternative_sizes.for_brands = i18n.brand_runs_large_tip_ar(request.brand or "")

        # Growth percentiles
        if rec.growth_percentile:
            ar.growth_percentile = GrowthPercentile(
                weight_percentile=i18n.PERCENTILE_AR.get(
                    rec.growth_percentile.weight_percentile or "",
                    rec.growth_percentile.weight_percentile,
                ),
                height_percentile=i18n.PERCENTILE_AR.get(
                    rec.growth_percentile.height_percentile or "",
                    rec.growth_percentile.height_percentile,
                ),
            )

        # Data source
        ar.data_source = i18n.DATA_SOURCE_AR.get(rec.data_source, rec.data_source)
        ar.lang = "ar"

        return ar


    async def _llm_enhance(
        self,
        request: SizeRequest,
        sizing_data: dict,
        growth_info: dict,
        rule_result: SizeRecommendation,
    ) -> SizeRecommendation:
        """
        Enhance the rule-based recommendation with LLM reasoning.
        The LLM gets the retrieved data + rule result as context,
        and produces more natural, helpful reasoning.
        """
        system_prompt = """You are a helpful baby clothing size advisor for Mumzworld, 
a Middle Eastern e-commerce platform. You help moms find the right size for their children.

IMPORTANT RULES:
1. Be honest about uncertainty — if data is limited, say so
2. Always err on the side of sizing up (kids grow fast)
3. Consider that different brands fit differently
4. Be warm and supportive in tone — shopping for kids should be fun, not stressful
5. If measurements seem unusual, gently flag it without being alarming

You will receive the child's measurements, sizing data retrieved from our database, 
growth chart analysis, and a preliminary rule-based recommendation.

Your job: Improve the reasoning to be more natural and helpful while preserving accuracy.
Return ONLY a JSON object with these fields:
- reasoning: string (enhanced, parent-friendly explanation)
- what_to_verify: list of strings
- additional_tips: string or null"""

        user_prompt = f"""Child's info:
- Age: {request.age_months} months
- Height: {request.height_cm or 'not provided'} cm
- Weight: {request.weight_kg or 'not provided'} kg
- Brand: {request.brand or 'no specific brand'}

Retrieved sizing data:
- Brand found: {sizing_data.get('brand_found')}
- Brand: {sizing_data.get('brand_name', 'generic')}
- Brand notes: {sizing_data.get('brand_notes', 'N/A')}
- Matched sizes: {json.dumps(sizing_data.get('matched_sizes', [])[:3])}

Growth chart analysis:
- Weight percentile: {growth_info.get('weight_percentile', 'N/A')}
- Height percentile: {growth_info.get('height_percentile', 'N/A')}
- Flags: {growth_info.get('flags', [])}

Rule-based recommendation:
- Size: {rule_result.recommended_size}
- Confidence: {rule_result.confidence.value}
- Current reasoning: {rule_result.reasoning}

Please enhance the reasoning to be more natural and parent-friendly. Return JSON only."""

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]

        # Parse LLM response — strip markdown fences if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            llm_output = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON, keeping rule-based reasoning")
            return rule_result

        # Merge LLM enhancements with rule-based result
        enhanced = rule_result.model_copy()
        if "reasoning" in llm_output:
            enhanced.reasoning = llm_output["reasoning"]
        if "what_to_verify" in llm_output:
            # Merge, don't replace
            existing = set(enhanced.what_to_verify)
            for item in llm_output["what_to_verify"]:
                if item not in existing:
                    enhanced.what_to_verify.append(item)
        enhanced.data_source = "llm_enhanced"

        return enhanced


# Module-level singleton
_recommender: Optional[SizeRecommender] = None


def get_recommender() -> SizeRecommender:
    global _recommender
    if _recommender is None:
        _recommender = SizeRecommender()
    return _recommender
