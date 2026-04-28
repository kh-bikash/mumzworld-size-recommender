"""
Arabic localization for the Mumzworld Size Recommender.

Provides native Arabic translations for all user-facing output.
These are NOT machine-translated — they're written as a native speaker would
express sizing guidance to an Arabic-speaking mom.
"""

from __future__ import annotations

# ─── Confidence Labels ───────────────────────────────────────────────────────

CONFIDENCE_AR = {
    "high": "ثقة عالية",
    "medium": "ثقة متوسطة",
    "low": "ثقة منخفضة",
}

# ─── Size Labels ─────────────────────────────────────────────────────────────

SIZE_LABELS_AR = {
    "Newborn": "حديث الولادة",
    "Newborn (NB)": "حديث الولادة",
    "Tiny Baby": "طفل صغير جداً",
    "0-3 months": "٠-٣ أشهر",
    "3 months": "٣ أشهر",
    "3-6 months": "٣-٦ أشهر",
    "6 months": "٦ أشهر",
    "6-9 months": "٦-٩ أشهر",
    "9 months": "٩ أشهر",
    "9-12 months": "٩-١٢ شهر",
    "12 months": "١٢ شهر",
    "12-18 months": "١٢-١٨ شهر",
    "18 months": "١٨ شهر",
    "18-24 months": "١٨-٢٤ شهر",
    "24 months": "٢٤ شهر",
    "Up to 3 months": "حتى ٣ أشهر",
    "2T": "٢T",
    "3T": "٣T",
    "4T": "٤T",
    "5T": "٥T",
    "2-3 years": "٢-٣ سنوات",
    "3-4 years": "٣-٤ سنوات",
    "4-5 years": "٤-٥ سنوات",
    "5+ years": "٥+ سنوات",
}

# ─── Reasoning Templates ────────────────────────────────────────────────────

def reasoning_size_match_ar(label: str, score: int, total: int) -> str:
    return f"المقاس '{label}' يتوافق مع {score}/{total} من القياسات المقدمة."

def reasoning_age_based_ar(age: int, label: str) -> str:
    return f"بناءً على العمر ({age} شهر)، المقاس '{label}' هو الأقرب."

def reasoning_no_match_ar(label: str) -> str:
    return f"لم يتم العثور على مقاس مطابق تماماً. نستخدم المقاس العام: '{label}'."

def reasoning_brand_chart_ar(brand: str, notes: str) -> str:
    return f"نستخدم جدول مقاسات {brand} ({notes})."

def reasoning_generic_ar() -> str:
    return "نستخدم المقاسات العامة المبنية على معايير منظمة الصحة العالمية (لم يتم تحديد ماركة)."

def reasoning_hw_override_ar(label: str) -> str:
    return f"الطول والوزن يشيران إلى '{label}'، وهو يختلف عن المقاس المبني على العمر. نستخدم المقاس المبني على القياسات."


# ─── Uncertainty Messages ────────────────────────────────────────────────────

UNCERTAINTY_AR = {
    "Limited measurements": {
        "flag": "قياسات محدودة",
        "detail": "تم تقديم العمر فقط. الطول والوزن يساعدان في تحديد المقاس الأنسب بدقة أكبر.",
    },
    "Brand not found": {
        "flag": "الماركة غير متوفرة",
        # detail is dynamic, constructed at runtime
    },
    "No exact match": {
        "flag": "لا يوجد تطابق دقيق",
        "detail": "القياسات المقدمة لا تقع ضمن نطاقات المقاسات المعتادة. قد يكون الطفل بين مقاسين.",
    },
    "Atypical weight": {
        "flag": "وزن غير معتاد",
    },
    "Atypical height": {
        "flag": "طول غير معتاد",
    },
    "LLM unavailable": {
        "flag": "الذكاء الاصطناعي غير متاح",
        "detail": "لم نتمكن من تحسين التوصية بالذكاء الاصطناعي — نستخدم المحرك القائم على القواعد فقط.",
    },
}

def brand_not_found_detail_ar(brand: str, available: list[str]) -> str:
    brands_str = "، ".join(available)
    return f"لا تتوفر لدينا بيانات مقاسات لماركة '{brand}' — نستخدم النطاقات العامة. الماركات المتاحة: {brands_str}"

def atypical_weight_detail_ar(weight: float, percentile: str, age: int) -> str:
    pctl_ar = PERCENTILE_AR.get(percentile, percentile)
    return f"الوزن ({weight} كغ) في {pctl_ar} لعمر {age} شهر — خارج النطاق المعتاد، قد يكون تحديد المقاس أقل دقة."

def atypical_height_detail_ar(height: float, percentile: str, age: int) -> str:
    pctl_ar = PERCENTILE_AR.get(percentile, percentile)
    return f"الطول ({height} سم) في {pctl_ar} لعمر {age} شهر — خارج النطاق المعتاد، قد يكون تحديد المقاس أقل دقة."


# ─── Verify / Tips ───────────────────────────────────────────────────────────

VERIFY_AR = {
    "Not all measurements align with this size -- check the size chart":
        "ليست كل القياسات متوافقة مع هذا المقاس — تحقق من جدول المقاسات",
    "Provide height and weight for a more accurate recommendation":
        "قدّم الطول والوزن للحصول على توصية أدق",
    "Consult the brand's size chart directly":
        "راجع جدول مقاسات الماركة مباشرة",
}

def brand_runs_small_verify_ar(brand: str) -> str:
    return f"مقاسات {brand} تميل لأن تكون صغيرة، تحقق من جدولهم"

def brand_runs_large_verify_ar(brand: str) -> str:
    return f"مقاسات {brand} تميل لأن تكون كبيرة، طفلك قد يناسبه مقاس أصغر"

def check_brand_chart_ar(brand: str) -> str:
    return f"تحقق من جدول مقاسات {brand} الخاص"


# ─── Alternative Sizes ───────────────────────────────────────────────────────

def between_sizes_ar(sizes: str) -> str:
    # Translate any English size labels in the sizes string
    translated = sizes
    for en, ar in SIZE_LABELS_AR.items():
        translated = translated.replace(en, ar)
    return f"الطفل بين مقاسين {translated} — اختر المقاس الأكبر ليكون مريحاً مع النمو.".replace(" or ", " أو ")

def when_in_doubt_ar() -> str:
    return "عند الشك، اختر المقاس الأكبر ليكون مريحاً مع النمو"

def brand_runs_small_tip_ar(brand: str) -> str:
    return f"مقاسات {brand} تميل لأن تكون صغيرة — فكّر في اختيار مقاس أكبر."

def brand_runs_large_tip_ar(brand: str) -> str:
    return f"مقاسات {brand} تميل لأن تكون كبيرة — طفلك قد يناسبه المقاس المحدد أو مقاس أصغر."


# ─── Percentile Labels ───────────────────────────────────────────────────────

PERCENTILE_AR = {
    "below 3rd": "أقل من المئوية ٣",
    "3rd-15th": "المئوية ٣-١٥",
    "15th-50th": "المئوية ١٥-٥٠",
    "50th-85th": "المئوية ٥٠-٨٥",
    "85th-97th": "المئوية ٨٥-٩٧",
    "above 97th": "أعلى من المئوية ٩٧",
}


# ─── Data Source Labels ──────────────────────────────────────────────────────

DATA_SOURCE_AR = {
    "rule_engine": "محرك القواعد",
    "llm_enhanced": "محسّن بالذكاء الاصطناعي",
    "llm_only": "الذكاء الاصطناعي فقط",
}
