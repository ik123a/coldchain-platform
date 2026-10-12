"""
Design Critique Agent powered by Gemini Reasoning.
Evaluates design references and UI concepts against Anti-AI-Slop principles.
"""
import os
import json
import logging
import requests
from typing import Dict, Any, Optional

log = logging.getLogger("coldchain.gemini.critique")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
CRITIQUE_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3-flash-preview")

ANTI_SLOP_RULES = [
    "Is this actually useful for real logistics dispatchers and fleet engineers?",
    "Is the information hierarchy crisp and immediate?",
    "Is there too much decoration, neon, or gratuitous gradients?",
    "Does it look like a generic crypto/SaaS AI dashboard?",
    "Are there too many competing cards on one screen?",
    "Is the map doing the visual heavy lifting (60–75% priority)?",
    "Does the motion communicate cause-and-effect state rather than eye candy?",
    "Could a real enterprise cold-chain company ship this interface tomorrow?",
    "Is the interface too futuristic, glowing, or cyberpunk?",
    "Could 20% of the visual elements be subtracted to improve clarity?"
]


def critique_reference_asset(asset_id: str, title: str, category: str, prompt: str) -> Dict[str, Any]:
    """
    Critique a design reference asset using Gemini reasoning.
    Returns structured JSON with scores and anti-slop assessment.

    HONESTY CONTRACT (the old behaviour was a lie): a missing key, an exhausted
    key pool, a provider error, or unparseable output previously returned
    `_fallback_critique` — hardcoded 9.x scores with verdict APPROVED — which a
    caller cannot distinguish from a real critique. Now every non-success is an
    explicit error with a machine-readable `status`:
      unavailable  — no credential configured
      rate_limited — provider returned 429
      failed       — provider error / network failure / malformed output
    Only a genuine 200 with parseable JSON returns scores.
    """
    if not GEMINI_API_KEY:
        return {"success": False, "status": "unavailable",
                "error": "GEMINI_API_KEY not configured; critique unavailable",
                "asset_id": asset_id}

    system_instruction = (
        "You are an elite product design director and anti-slop design critic evaluating UI/UX concepts "
        "for 'ColdChain Rescue', a mission-critical cold-chain logistics digital twin. "
        "Strictly penalize generic AI aesthetics (neon gradients, floating glowing brains, excessive cards, futuristic clutter). "
        "Heavily reward restraint, calm dark surfaces (#080A0F), spatial hierarchy, progressive disclosure, and crisp enterprise utility."
    )

    user_query = f"""
Analyze this design reference:
Asset ID: {asset_id}
Title: {title}
Category: {category}
Prompt Description: {prompt}

Evaluate against the 10 Anti-AI-Slop Rules:
1. Actually useful?
2. Information hierarchy?
3. Free of decorative slop?
4. Distinct from generic AI SaaS?
5. Not overcrowded?
6. Map dominant?
7. Motion meaningful?
8. Shippable by real enterprise?
9. Grounded (not sci-fi)?
10. Can 20% be removed?

Provide a structured JSON response with:
{{
  "asset_id": "{asset_id}",
  "scores": {{
    "visual_quality": <number 1-10>,
    "information_hierarchy": <number 1-10>,
    "simplicity": <number 1-10>,
    "originality": <number 1-10>,
    "logistics_fit": <number 1-10>,
    "ai_slop_risk": <number 1-10 where 1 is zero slop and 10 is high slop>,
    "motion_quality": <number 1-10>
  }},
  "overall_verdict": "APPROVED" | "NEEDS_REFINEMENT" | "REJECTED",
  "strengths": ["...", "..."],
  "subtractions_recommended": ["...", "..."],
  "critique_summary": "..."
}}
Output ONLY valid JSON.
"""

    # API keys come from the environment ONLY. This list previously carried two
    # hardcoded Google/Gemini keys as trailing fallbacks, which put live
    # credentials in tracked source -- and because the literal was last in the
    # list, the service would keep working with the embedded key even if the env
    # vars were removed. Do not re-add literals here; put keys in backend/.env.
    # (Tests monkeypatch module attrs; read them defensively so a patched
    # GEMINI_API_KEY is honoured without touching os.environ.)
    candidate_keys = [k for k in [
        GEMINI_API_KEY or os.getenv("GEMINI_API_KEY"),
        os.getenv("GEMINI_API_KEY_BACKUP"),
        os.getenv("GOOGLE_API_KEY"),
    ] if k]
    candidate_models = [
        os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash"),
        os.getenv("GEMINI_FALLBACK_TEXT_MODEL", "gemini-3-flash-preview")
    ]

    for key in candidate_keys:
        for model in candidate_models:
            # Key in the header, not the query string (see image_generation).
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": f"{system_instruction}\n\n{user_query}"}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2
                }
            }
            try:
                resp = requests.post(url, json=payload, timeout=20,
                                     headers={"Content-Type": "application/json",
                                              "x-goog-api-key": key})
                if resp.status_code == 200:
                    data = resp.json()
                    cand = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    try:
                        parsed = json.loads(cand)
                    except (ValueError, TypeError):
                        log.warning("critique output was not valid JSON (model=%s)", model)
                        continue
                    if not isinstance(parsed, dict) or "overall_verdict" not in parsed:
                        log.warning("critique output incomplete (model=%s); "
                                    "refusing to fabricate a verdict", model)
                        continue
                    parsed["asset_id"] = parsed.get("asset_id", asset_id)
                    return parsed
                elif resp.status_code == 429:
                    log.warning("critique rate limited by provider (model=%s)", model)
                    return {"success": False, "status": "rate_limited",
                            "error": "critique provider rate limited; retry later",
                            "asset_id": asset_id}
                else:
                    log.warning("Key/Model (%s) returned %s, trying next...",
                                model, resp.status_code)
            except requests.Timeout:
                log.warning("critique provider timeout (model=%s)", model)
            except Exception as e:
                # Exception text can embed request details; keep it categorical.
                log.warning("Critique attempt on %s failed: %s", model,
                            type(e).__name__)

    log.warning("all critique keys/models exhausted; returning explicit failure")
    return {"success": False, "status": "failed",
            "error": "critique provider failed; no verdict available",
            "asset_id": asset_id}
