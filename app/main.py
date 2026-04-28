"""
Mumzworld Smart Size Recommender — FastAPI Application

Main API server exposing:
- POST /recommend — Get a size recommendation
- GET /brands — List available brands
- GET /health — Health check
- GET / — Interactive demo page
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .models import SizeRecommendation, SizeRequest
from .recommender import get_recommender
from .retriever import get_retriever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mumzworld Smart Size Recommender",
    description=(
        "AI-powered size recommendation engine for baby/kids clothing. "
        "Combines brand sizing data (RAG), WHO growth charts, and optional LLM enhancement "
        "to help moms find the right size for their children."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    recommender = get_recommender()
    return {
        "status": "healthy",
        "llm_available": recommender.llm_available,
        "brands_loaded": len(get_retriever().available_brands),
    }


@app.get("/brands")
async def list_brands():
    """List all available brands with sizing data."""
    retriever = get_retriever()
    brands_info = []
    for name in retriever.available_brands:
        info = retriever.get_brand_info(name)
        if info:
            brands_info.append({
                "name": info["brand_name"],
                "region": info.get("region"),
                "runs": info.get("runs"),
                "sizing_notes": info.get("sizing_notes"),
                "num_sizes": len(info.get("sizes", [])),
            })
    return {"brands": brands_info}


@app.post("/recommend", response_model=SizeRecommendation)
async def recommend_size(request: SizeRequest):
    """
    Get a size recommendation for a child.
    
    Accepts age (required), height, weight, and optional brand.
    Returns structured recommendation with confidence level and uncertainty flags.
    """
    try:
        recommender = get_recommender()
        result = await recommender.recommend(request)
        return result
    except Exception as e:
        logger.error(f"Recommendation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def demo_page():
    """Interactive demo page for testing the recommender."""
    return HTMLResponse(content=DEMO_HTML)


# ─── Demo Page HTML ──────────────────────────────────────────────────────────

DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mumzworld Size Recommender</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: rgba(255, 255, 255, 0.03);
            --border: rgba(255, 255, 255, 0.08);
            --text-primary: #f0f0f5;
            --text-secondary: #8888a0;
            --text-muted: #55556a;
            --accent: #7c5cfc;
            --accent-glow: rgba(124, 92, 252, 0.15);
            --success: #34d399;
            --warning: #fbbf24;
            --error: #f87171;
            --radius: 16px;
        }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        .bg-grid {
            position: fixed;
            inset: 0;
            background-image: 
                linear-gradient(rgba(124, 92, 252, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(124, 92, 252, 0.03) 1px, transparent 1px);
            background-size: 60px 60px;
            pointer-events: none;
            z-index: 0;
        }

        .bg-glow {
            position: fixed;
            width: 600px;
            height: 600px;
            border-radius: 50%;
            filter: blur(120px);
            opacity: 0.08;
            pointer-events: none;
            z-index: 0;
        }

        .bg-glow-1 { top: -200px; left: -100px; background: #7c5cfc; }
        .bg-glow-2 { bottom: -200px; right: -100px; background: #34d399; }

        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 24px;
            position: relative;
            z-index: 1;
        }

        header {
            text-align: center;
            margin-bottom: 48px;
        }

        .badge {
            display: inline-block;
            padding: 6px 16px;
            background: var(--accent-glow);
            border: 1px solid rgba(124, 92, 252, 0.2);
            border-radius: 100px;
            font-size: 12px;
            font-weight: 500;
            color: var(--accent);
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 16px;
        }

        h1 {
            font-size: 40px;
            font-weight: 700;
            letter-spacing: -1px;
            background: linear-gradient(135deg, #fff 0%, #8888a0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
        }

        .subtitle {
            color: var(--text-secondary);
            font-size: 16px;
            line-height: 1.6;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 32px;
            backdrop-filter: blur(20px);
            transition: border-color 0.3s ease;
        }

        .card:hover { border-color: rgba(255, 255, 255, 0.12); }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .form-group.full-width {
            grid-column: 1 / -1;
        }

        label {
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
            letter-spacing: 0.3px;
        }

        input, select {
            padding: 12px 16px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text-primary);
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            outline: none;
            transition: all 0.2s ease;
        }

        input:focus, select:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }

        input::placeholder { color: var(--text-muted); }

        select option { background: var(--bg-secondary); color: var(--text-primary); }

        .btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #7c5cfc, #5a3fd4);
            border: none;
            border-radius: 10px;
            color: white;
            font-family: 'Inter', sans-serif;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            letter-spacing: 0.3px;
        }

        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 30px rgba(124, 92, 252, 0.3);
        }

        .btn:active { transform: translateY(0); }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .result-card {
            margin-top: 32px;
            animation: fadeIn 0.4s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(12px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .result-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }

        .size-display {
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .confidence-badge {
            padding: 6px 14px;
            border-radius: 100px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .confidence-high {
            background: rgba(52, 211, 153, 0.12);
            color: var(--success);
            border: 1px solid rgba(52, 211, 153, 0.2);
        }

        .confidence-medium {
            background: rgba(251, 191, 36, 0.12);
            color: var(--warning);
            border: 1px solid rgba(251, 191, 36, 0.2);
        }

        .confidence-low {
            background: rgba(248, 113, 113, 0.12);
            color: var(--error);
            border: 1px solid rgba(248, 113, 113, 0.2);
        }

        .result-section {
            margin-bottom: 20px;
        }

        .result-section h3 {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }

        .result-section p {
            color: var(--text-primary);
            font-size: 14px;
            line-height: 1.7;
        }

        .tag-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .tag {
            padding: 6px 12px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 13px;
            color: var(--text-secondary);
        }

        .uncertainty-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .uncertainty-item {
            padding: 12px 16px;
            background: rgba(251, 191, 36, 0.05);
            border: 1px solid rgba(251, 191, 36, 0.12);
            border-radius: 10px;
        }

        .uncertainty-item strong {
            color: var(--warning);
            font-size: 13px;
        }

        .uncertainty-item p {
            color: var(--text-secondary);
            font-size: 13px;
            margin-top: 4px;
        }

        .source-badge {
            display: inline-block;
            margin-top: 16px;
            padding: 4px 10px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 11px;
            color: var(--text-muted);
        }

        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .lang-toggle {
            display: flex;
            justify-content: center;
            gap: 8px;
            margin-bottom: 24px;
        }

        .lang-btn {
            padding: 8px 20px;
            border-radius: 100px;
            border: 1px solid var(--border);
            background: transparent;
            color: var(--text-secondary);
            font-family: 'Inter', sans-serif;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .lang-btn.active {
            background: var(--accent-glow);
            border-color: rgba(124, 92, 252, 0.3);
            color: var(--accent);
        }

        .rtl { direction: rtl; text-align: right; }

        @media (max-width: 600px) {
            .form-grid { grid-template-columns: 1fr; }
            h1 { font-size: 28px; }
            .container { padding: 24px 16px; }
        }
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    <div class="bg-glow bg-glow-1"></div>
    <div class="bg-glow bg-glow-2"></div>

    <div class="container">
        <header>
            <div class="badge">AI-Powered</div>
            <h1>Mumzworld Size Recommender</h1>
            <p class="subtitle">
                Find the perfect fit for your little one. Enter your child's measurements 
                and get an instant, AI-powered size recommendation.
            </p>
        </header>

        <div class="lang-toggle">
            <button class="lang-btn active" id="langEn" onclick="setLang('en')">English</button>
            <button class="lang-btn" id="langAr" onclick="setLang('ar')">العربية</button>
        </div>

        <div class="card">
            <form id="sizeForm">
                <div class="form-grid">
                    <div class="form-group">
                        <label for="age_months">Age (months) *</label>
                        <input type="number" id="age_months" name="age_months" 
                               placeholder="e.g. 18" min="0" max="120" required>
                    </div>
                    <div class="form-group">
                        <label for="height_cm">Height (cm)</label>
                        <input type="number" id="height_cm" name="height_cm" 
                               placeholder="e.g. 82" min="30" max="160" step="0.1">
                    </div>
                    <div class="form-group">
                        <label for="weight_kg">Weight (kg)</label>
                        <input type="number" id="weight_kg" name="weight_kg" 
                               placeholder="e.g. 11" min="1" max="50" step="0.1">
                    </div>
                    <div class="form-group">
                        <label for="brand">Brand (optional)</label>
                        <select id="brand" name="brand">
                            <option value="">Any / No preference</option>
                            <option value="Carter's">Carter's</option>
                            <option value="H&M Kids">H&M Kids</option>
                            <option value="Zara Baby">Zara Baby</option>
                            <option value="Mothercare">Mothercare</option>
                            <option value="BabyShop">BabyShop</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn" id="submitBtn">
                    Get Size Recommendation
                </button>
            </form>
        </div>

        <div id="result"></div>
    </div>

    <script>
        const form = document.getElementById('sizeForm');
        const resultDiv = document.getElementById('result');
        const submitBtn = document.getElementById('submitBtn');
        let currentLang = 'en';

        function setLang(lang) {
            currentLang = lang;
            document.getElementById('langEn').classList.toggle('active', lang === 'en');
            document.getElementById('langAr').classList.toggle('active', lang === 'ar');
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span>' + (currentLang === 'ar' ? '...جارٍ التحليل' : 'Analyzing...');
            resultDiv.innerHTML = '';

            const body = {
                age_months: parseInt(document.getElementById('age_months').value),
                lang: currentLang,
            };

            const height = document.getElementById('height_cm').value;
            const weight = document.getElementById('weight_kg').value;
            const brand = document.getElementById('brand').value;

            if (height) body.height_cm = parseFloat(height);
            if (weight) body.weight_kg = parseFloat(weight);
            if (brand) body.brand = brand;

            try {
                const resp = await fetch('/recommend', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });

                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const data = await resp.json();
                renderResult(data);
            } catch (err) {
                resultDiv.innerHTML = `
                    <div class="card result-card" style="border-color: rgba(248,113,113,0.3);">
                        <p style="color: var(--error);">Error: ${err.message}</p>
                    </div>`;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = currentLang === 'ar' ? 'احصل على توصية المقاس' : 'Get Size Recommendation';
            }
        });

        function renderResult(data) {
            const confClass = `confidence-${data.confidence}`;
            const isAr = data.lang === 'ar';
            const rtl = isAr ? ' rtl' : '';
            
            const labels = isAr ? {
                reasoning: '\u0627\u0644\u062a\u0641\u0633\u064a\u0631',
                growth: '\u0646\u0633\u0628 \u0627\u0644\u0646\u0645\u0648',
                verify: '\u062a\u062d\u0642\u0642 \u0645\u0646',
                tips: '\u0646\u0635\u0627\u0626\u062d \u0627\u0644\u0645\u0642\u0627\u0633',
                uncertainty: '\u062a\u0646\u0628\u064a\u0647\u0627\u062a \u0639\u062f\u0645 \u0627\u0644\u064a\u0642\u064a\u0646',
                weight: '\u0627\u0644\u0648\u0632\u0646',
                height: '\u0627\u0644\u0637\u0648\u0644',
                source: '\u0627\u0644\u0645\u0635\u062f\u0631',
                confidence: '\u062b\u0642\u0629',
            } : {
                reasoning: 'Reasoning',
                growth: 'Growth Percentiles',
                verify: 'What to Verify',
                tips: 'Sizing Tips',
                uncertainty: 'Uncertainty Flags',
                weight: 'Weight',
                height: 'Height',
                source: 'Source',
                confidence: 'confidence',
            };
            
            let html = `<div class="card result-card${rtl}">`;
            
            // Header
            html += `<div class="result-header">
                <span class="size-display">${data.recommended_size}</span>
                <span class="confidence-badge ${confClass}">${data.confidence} ${labels.confidence}</span>
            </div>`;

            // Reasoning
            html += `<div class="result-section">
                <h3>${labels.reasoning}</h3>
                <p>${data.reasoning}</p>
            </div>`;

            // Growth percentiles
            if (data.growth_percentile) {
                const gp = data.growth_percentile;
                html += `<div class="result-section">
                    <h3>${labels.growth}</h3>
                    <div class="tag-list">`;
                if (gp.weight_percentile) html += `<span class="tag">${labels.weight}: ${gp.weight_percentile}</span>`;
                if (gp.height_percentile) html += `<span class="tag">${labels.height}: ${gp.height_percentile}</span>`;
                html += `</div></div>`;
            }

            // What to verify
            if (data.what_to_verify && data.what_to_verify.length > 0) {
                html += `<div class="result-section">
                    <h3>${labels.verify}</h3>
                    <div class="tag-list">`;
                data.what_to_verify.forEach(item => {
                    html += `<span class="tag">${item}</span>`;
                });
                html += `</div></div>`;
            }

            // Alternatives
            const alt = data.alternative_sizes;
            if (alt && (alt.if_between_sizes || alt.for_brands)) {
                html += `<div class="result-section">
                    <h3>${labels.tips}</h3>`;
                if (alt.if_between_sizes) html += `<p>${alt.if_between_sizes}</p>`;
                if (alt.for_brands) html += `<p style="margin-top:6px">${alt.for_brands}</p>`;
                html += `</div>`;
            }

            // Uncertainties
            if (data.uncertainties && data.uncertainties.length > 0) {
                html += `<div class="result-section">
                    <h3>${labels.uncertainty}</h3>
                    <div class="uncertainty-list">`;
                data.uncertainties.forEach(u => {
                    html += `<div class="uncertainty-item">
                        <strong>${u.flag}</strong>
                        <p>${u.detail}</p>
                    </div>`;
                });
                html += `</div></div>`;
            }

            // Source
            html += `<span class="source-badge">${labels.source}: ${data.data_source}</span>`;
            html += `</div>`;

            resultDiv.innerHTML = html;
        }
    </script>
</body>
</html>"""
