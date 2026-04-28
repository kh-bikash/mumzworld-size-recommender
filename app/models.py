"""
Pydantic models for the Mumzworld Smart Size Recommender.

Provides structured input/output validation with clear types and constraints.
This is one of the core technical requirements: structured output with validation.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ─── Enums ────────────────────────────────────────────────────────────────────

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Language(str, Enum):
    EN = "en"
    AR = "ar"


# ─── Request Models ──────────────────────────────────────────────────────────

class SizeRequest(BaseModel):
    """Input from a parent looking for size recommendations."""

    age_months: int = Field(
        ...,
        ge=0,
        le=120,
        description="Child's age in months (0-120)",
    )
    height_cm: Optional[float] = Field(
        default=None,
        ge=30.0,
        le=160.0,
        description="Child's height in centimeters",
    )
    weight_kg: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=50.0,
        description="Child's weight in kilograms",
    )
    brand: Optional[str] = Field(
        default=None,
        description="Brand name (e.g. 'Carter\\'s', 'H&M Kids', 'Zara Baby')",
    )
    lang: Language = Field(
        default=Language.EN,
        description="Output language: 'en' for English, 'ar' for Arabic",
    )

    @field_validator("brand")
    @classmethod
    def normalize_brand(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


# ─── Response Models ─────────────────────────────────────────────────────────

class AlternativeSizes(BaseModel):
    """Guidance when the child is between sizes or brand-specific notes apply."""

    if_between_sizes: Optional[str] = Field(
        default=None,
        description="Advice if child falls between two sizes",
    )
    for_brands: Optional[str] = Field(
        default=None,
        description="Brand-specific sizing tips",
    )


class GrowthPercentile(BaseModel):
    """Where the child falls on growth charts."""

    weight_percentile: Optional[str] = Field(
        default=None,
        description="Approximate weight percentile range (e.g. '50th-85th')",
    )
    height_percentile: Optional[str] = Field(
        default=None,
        description="Approximate height percentile range (e.g. '15th-50th')",
    )


class UncertaintyFlag(BaseModel):
    """Explicit uncertainty disclosure."""

    flag: str = Field(..., description="What is uncertain")
    detail: str = Field(..., description="Why and what to do about it")


class SizeRecommendation(BaseModel):
    """
    The full recommendation returned to the parent.
    Validated output ensures consistency across rule-based and LLM paths.
    """

    recommended_size: str = Field(
        ...,
        description="The recommended size label (e.g. '18-24 months', '86 (12-18M)')",
    )
    confidence: Confidence = Field(
        ...,
        description="How confident the system is in this recommendation",
    )
    reasoning: str = Field(
        ...,
        min_length=10,
        description="Human-readable explanation of how we arrived at this size",
    )
    what_to_verify: list[str] = Field(
        default_factory=list,
        description="Things the parent should double-check",
    )
    alternative_sizes: AlternativeSizes = Field(
        default_factory=AlternativeSizes,
        description="Guidance for edge cases and brand-specific notes",
    )
    growth_percentile: Optional[GrowthPercentile] = Field(
        default=None,
        description="Where the child falls on WHO growth charts",
    )
    uncertainties: list[UncertaintyFlag] = Field(
        default_factory=list,
        description="Explicit uncertainty disclosures — the system is honest about what it doesn't know",
    )
    data_source: str = Field(
        default="rule_engine",
        description="Whether this came from 'rule_engine', 'llm_enhanced', or 'llm_only'",
    )
    lang: str = Field(
        default="en",
        description="Language of this response: 'en' or 'ar'",
    )


# ─── Eval Models ─────────────────────────────────────────────────────────────

class EvalResult(BaseModel):
    """Result of a single evaluation test case."""

    test_id: str
    test_name: str
    input: SizeRequest
    expected_size: Optional[str] = None
    expected_confidence: Optional[Confidence] = None
    should_express_uncertainty: bool = False
    actual_output: Optional[SizeRecommendation] = None
    size_correct: Optional[bool] = None
    confidence_correct: Optional[bool] = None
    uncertainty_expressed: Optional[bool] = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str = ""


class EvalSummary(BaseModel):
    """Summary of a full evaluation run."""

    total_tests: int
    passed: int
    failed: int
    average_score: float
    results: list[EvalResult]
