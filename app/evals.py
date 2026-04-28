"""
Evaluation suite for the Mumzworld Smart Size Recommender.

Contains 15 test cases:
- 7 standard cases (clear-cut sizing)
- 5 edge cases (between sizes, missing data)
- 3 adversarial cases (atypical measurements, unknown brands)

Scoring rubric:
- Size match: 40% (does recommended size match expected?)
- Confidence match: 20% (is confidence level appropriate?)
- Uncertainty handling: 30% (does it flag what it should?)
- Completeness: 10% (reasoning, tips, verify items present?)

Run with: python -m app.evals
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Add parent to path for module imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Confidence, EvalResult, EvalSummary, SizeRequest
from app.recommender import get_recommender

# ─── Test Cases ──────────────────────────────────────────────────────────────

TEST_CASES: list[dict] = [
    # ── Standard Cases ────────────────────────────────────────────────────
    {
        "id": "STD-01",
        "name": "Typical 18mo with Carter's — clear match",
        "input": {"age_months": 18, "height_cm": 82, "weight_kg": 11, "brand": "Carter's"},
        "expected_size": "18 months",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "18mo is at boundary between Carter's 18M and 24M ranges -- medium confidence is correct",
    },
    {
        "id": "STD-02",
        "name": "6-month-old, generic sizing",
        "input": {"age_months": 6, "height_cm": 67, "weight_kg": 7.5},
        "expected_size": "3-6 months",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "Standard measurements, no brand, should use generic chart",
    },
    {
        "id": "STD-03",
        "name": "12-month H&M Kids",
        "input": {"age_months": 12, "height_cm": 76, "weight_kg": 10, "brand": "H&M Kids"},
        "expected_size": "80 (9-12M)",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "H&M uses height-based EU sizing, child is at 76cm",
    },
    {
        "id": "STD-04",
        "name": "Newborn, Mothercare",
        "input": {"age_months": 0, "height_cm": 50, "weight_kg": 3.2, "brand": "Mothercare"},
        "expected_size": "Newborn",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "Clear newborn range for Mothercare",
    },
    {
        "id": "STD-05",
        "name": "3-year-old, Zara Baby",
        "input": {"age_months": 36, "height_cm": 96, "weight_kg": 14.5, "brand": "Zara Baby"},
        "expected_size": "98 (2-3Y)",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "3-year-old at 96cm, right in Zara's 98 range",
    },
    {
        "id": "STD-06",
        "name": "24-month BabyShop",
        "input": {"age_months": 24, "height_cm": 88, "weight_kg": 13, "brand": "BabyShop"},
        "expected_size": "18-24 months",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "Measurements squarely in BabyShop 18-24M range",
    },
    {
        "id": "STD-07",
        "name": "9-month-old, no brand",
        "input": {"age_months": 9, "height_cm": 72, "weight_kg": 9.0},
        "expected_size": "6-9 months",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "WHO chart typical measurements for 9 months",
    },

    # ── Edge Cases ────────────────────────────────────────────────────────
    {
        "id": "EDGE-01",
        "name": "Age only — no height or weight",
        "input": {"age_months": 12},
        "expected_size": "9-12 months",
        "expected_confidence": "medium",
        "should_express_uncertainty": True,
        "notes": "Missing measurements should trigger uncertainty about accuracy",
    },
    {
        "id": "EDGE-02",
        "name": "Between sizes — tall for age",
        "input": {"age_months": 12, "height_cm": 80, "weight_kg": 9.5, "brand": "Carter's"},
        "expected_size": "18 months",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "Height pushes toward 12M but weight is lower, should note between sizes",
    },
    {
        "id": "EDGE-03",
        "name": "Max age boundary (5 years = 60 months)",
        "input": {"age_months": 60, "height_cm": 110, "weight_kg": 19},
        "expected_size": "4-5 years",
        "expected_confidence": "medium",
        "should_express_uncertainty": False,
        "notes": "Upper end of supported age range",
    },
    {
        "id": "EDGE-04",
        "name": "Premature baby — very small newborn",
        "input": {"age_months": 0, "height_cm": 40, "weight_kg": 1.5, "brand": "Mothercare"},
        "expected_size": "Tiny Baby",
        "expected_confidence": "low",
        "should_express_uncertainty": True,
        "notes": "Measurements below typical newborn range — should flag atypical",
    },
    {
        "id": "EDGE-05",
        "name": "Conflicting measurements — heavy but short",
        "input": {"age_months": 18, "height_cm": 75, "weight_kg": 14},
        "expected_size": "18-24 months",
        "expected_confidence": "medium",
        "should_express_uncertainty": True,
        "notes": "Height says smaller, weight says bigger. Should note conflict.",
    },

    # ── Adversarial Cases ─────────────────────────────────────────────────
    {
        "id": "ADV-01",
        "name": "Unknown brand — 'Petit Bateau'",
        "input": {"age_months": 18, "height_cm": 82, "weight_kg": 11, "brand": "Petit Bateau"},
        "expected_size": "12-18 months",
        "expected_confidence": "medium",
        "should_express_uncertainty": True,
        "notes": "Brand not in database — MUST express uncertainty about brand data",
    },
    {
        "id": "ADV-02",
        "name": "Extreme outlier — very large 12-month-old",
        "input": {"age_months": 12, "height_cm": 85, "weight_kg": 14},
        "expected_size": "18-24 months",
        "expected_confidence": "low",
        "should_express_uncertainty": True,
        "notes": "Above 97th percentile for both — must flag as atypical",
    },
    {
        "id": "ADV-03",
        "name": "Older child outside typical range (8 years = 96 months)",
        "input": {"age_months": 96, "height_cm": 130, "weight_kg": 28},
        "expected_size": "5+ years",
        "expected_confidence": "low",
        "should_express_uncertainty": True,
        "notes": "Beyond our detailed sizing data — should acknowledge limitation",
    },
]


# ─── Scoring Logic ───────────────────────────────────────────────────────────

def score_test_case(test: dict, result) -> EvalResult:
    """
    Score a single test case result.
    
    Rubric:
    - Size match (40%): Does the recommended size match expected?
      Partial credit for close matches (e.g. one size off)
    - Confidence match (20%): Is confidence level appropriate?
    - Uncertainty handling (30%): Does it flag uncertainty when it should?
    - Completeness (10%): Are reasoning/tips/verify items present?
    """
    score = 0.0
    notes_parts = []

    req = SizeRequest(**test["input"])
    expected_size = test.get("expected_size")
    expected_conf = test.get("expected_confidence")
    should_uncertain = test.get("should_express_uncertainty", False)

    # 1. Size match (40%)
    size_correct = False
    if expected_size and result:
        actual = result.recommended_size.lower().strip()
        expected = expected_size.lower().strip()
        if expected in actual or actual in expected:
            score += 0.40
            size_correct = True
            notes_parts.append("[OK] Size: correct")
        else:
            notes_parts.append(f"[FAIL] Size: expected '{expected_size}', got '{result.recommended_size}'")

    # 2. Confidence match (20%)
    conf_correct = False
    if expected_conf and result:
        if result.confidence.value == expected_conf:
            score += 0.20
            conf_correct = True
            notes_parts.append("[OK] Confidence: correct")
        elif (
            (expected_conf == "high" and result.confidence.value == "medium")
            or (expected_conf == "medium" and result.confidence.value in ("high", "low"))
            or (expected_conf == "low" and result.confidence.value == "medium")
        ):
            score += 0.10  # Partial credit for adjacent confidence
            notes_parts.append(
                f"[WARN] Confidence: expected '{expected_conf}', got '{result.confidence.value}' (partial)"
            )
        else:
            notes_parts.append(
                f"[FAIL] Confidence: expected '{expected_conf}', got '{result.confidence.value}'"
            )

    # 3. Uncertainty handling (30%)
    uncertainty_expressed = False
    if result:
        has_uncertainties = len(result.uncertainties) > 0
        uncertainty_expressed = has_uncertainties

        if should_uncertain:
            if has_uncertainties:
                score += 0.30
                notes_parts.append("[OK] Uncertainty: correctly flagged")
            else:
                notes_parts.append("[FAIL] Uncertainty: should have flagged uncertainty but didn't")
        else:
            if not has_uncertainties:
                score += 0.30
                notes_parts.append("[OK] Uncertainty: correctly did NOT flag (no uncertainty expected)")
            else:
                score += 0.15  # Partial — being cautious is better than being silent
                notes_parts.append("[WARN] Uncertainty: flagged uncertainty when not required (overly cautious)")

    # 4. Completeness (10%)
    if result:
        completeness = 0
        if result.reasoning and len(result.reasoning) > 20:
            completeness += 1
        if len(result.what_to_verify) > 0:
            completeness += 1
        if result.alternative_sizes.if_between_sizes or result.alternative_sizes.for_brands:
            completeness += 1

        comp_score = (completeness / 3) * 0.10
        score += comp_score
        if completeness == 3:
            notes_parts.append("[OK] Completeness: full")
        else:
            notes_parts.append(f"[WARN] Completeness: {completeness}/3 fields populated")

    return EvalResult(
        test_id=test["id"],
        test_name=test["name"],
        input=req,
        expected_size=expected_size,
        expected_confidence=Confidence(expected_conf) if expected_conf else None,
        should_express_uncertainty=should_uncertain,
        actual_output=result,
        size_correct=size_correct,
        confidence_correct=conf_correct,
        uncertainty_expressed=uncertainty_expressed,
        score=round(min(score, 1.0), 2),
        notes=" | ".join(notes_parts),
    )


# ─── Runner ──────────────────────────────────────────────────────────────────

async def run_evals() -> EvalSummary:
    """Run all evaluation test cases and produce a summary."""
    recommender = get_recommender()
    results: list[EvalResult] = []
    
    print("=" * 70)
    print("MUMZWORLD SIZE RECOMMENDER -- EVALUATION SUITE")
    print("=" * 70)
    print(f"\nRunning {len(TEST_CASES)} test cases...\n")

    for i, test in enumerate(TEST_CASES, 1):
        print(f"[{i:2d}/{len(TEST_CASES)}] {test['id']}: {test['name']}")
        
        try:
            req = SizeRequest(**test["input"])
            result = await recommender.recommend(req)
            eval_result = score_test_case(test, result)
        except Exception as e:
            eval_result = EvalResult(
                test_id=test["id"],
                test_name=test["name"],
                input=SizeRequest(**test["input"]),
                score=0.0,
                notes=f"[FAIL] EXCEPTION: {e}",
            )

        results.append(eval_result)
        
        status = "PASS" if eval_result.score >= 0.7 else "FAIL" if eval_result.score < 0.4 else "PARTIAL"
        color = {"PASS": "[PASS]", "FAIL": "[FAIL]", "PARTIAL": "[PART]"}[status]
        print(f"       {color} Score: {eval_result.score:.2f} -- {eval_result.notes}")
        if eval_result.actual_output:
            print(f"       -> Size: {eval_result.actual_output.recommended_size} "
                  f"({eval_result.actual_output.confidence.value})")
        print()

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.score >= 0.7)
    failed = total - passed
    avg = sum(r.score for r in results) / total if total else 0

    summary = EvalSummary(
        total_tests=total,
        passed=passed,
        failed=failed,
        average_score=round(avg, 3),
        results=results,
    )

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total:    {total}")
    print(f"  Passed:   {passed} (score >= 0.7)")
    print(f"  Failed:   {failed}")
    print(f"  Average:  {avg:.1%}")
    print()

    # Category breakdown
    std_results = [r for r in results if r.test_id.startswith("STD")]
    edge_results = [r for r in results if r.test_id.startswith("EDGE")]
    adv_results = [r for r in results if r.test_id.startswith("ADV")]

    for label, group in [("Standard", std_results), ("Edge", edge_results), ("Adversarial", adv_results)]:
        if group:
            grp_avg = sum(r.score for r in group) / len(group)
            grp_pass = sum(1 for r in group if r.score >= 0.7)
            print(f"  {label}: {grp_avg:.1%} avg ({grp_pass}/{len(group)} passed)")

    print("=" * 70)

    # Save results to JSON
    output_path = Path(__file__).resolve().parent.parent / "eval_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary.model_dump(), f, indent=2, default=str)
    print(f"\nFull results saved to: {output_path}")

    return summary


if __name__ == "__main__":
    asyncio.run(run_evals())
