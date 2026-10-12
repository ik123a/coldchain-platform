"""
Gemini Image Generation Service.
Implements the reference generation service using Google's latest models:
- Primary: gemini-3.1-flash-image (Nano Banana 2)
- Premium: gemini-3-pro-image (Nano Banana Pro)
"""
import os
import base64
import logging
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any

log = logging.getLogger("coldchain.gemini.image")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
DEFAULT_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
PREMIUM_IMAGE_MODEL = os.getenv("GEMINI_PREMIUM_IMAGE_MODEL", "gemini-3-pro-image")

ASPECT_RATIOS = ["1:1", "4:3", "3:2", "16:9", "21:9", "9:16"]


def generate_reference_image(
    prompt: str,
    aspect_ratio: str = "16:9",
    model: str = DEFAULT_IMAGE_MODEL,
    output_path: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate a high-fidelity visual reference image using Gemini 3.1 Flash Image or 3 Pro Image.
    Supports reference images for visual consistency (multi-image input).
    """
    if not GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY is not configured.")
        return {"success": False, "error": "GEMINI_API_KEY missing"}

    if aspect_ratio not in ASPECT_RATIOS:
        aspect_ratio = "16:9"

    # API keys come from the environment ONLY. This list previously carried two
    # hardcoded Google/Gemini keys as trailing fallbacks, which put live
    # credentials in tracked source -- and because the literal was last in the
    # list, the service would keep working with the embedded key even if the env
    # vars were removed. Do not re-add literals here; put keys in backend/.env.
    candidate_keys = [k for k in [
        os.getenv("GEMINI_API_KEY"),
        os.getenv("GEMINI_API_KEY_BACKUP"),
        os.getenv("GOOGLE_API_KEY"),
    ] if k]

    # Validate references BEFORE building the request or touching the network.
    # The old behaviour — skip the rejected entry and generate anyway — meant a
    # request the caller was not authorized to make still produced a billable
    # call. Fail closed: a refused reference must cost nothing. (The route layer
    # already rejects this earlier; this is the service's own guard.)
    if reference_images:
        from .safe_paths import resolve_reference, ReferenceRejected
        for ref in reference_images[:3]:
            try:
                resolve_reference(ref)
            except ReferenceRejected as e:
                log.warning("generation refused, reference rejected: %s", e)
                return {"success": False, "error": f"reference rejected: {e}",
                        "rejected_reference": True}

    # Build prompt parts. Only approved references (validated above) are read.
    parts: List[Dict[str, Any]] = [{"text": prompt}]
    if reference_images:
        from .safe_paths import read_reference
        for ref in reference_images[:3]:
            raw, mime = read_reference(ref)
            parts.append({
                "inlineData": {
                    "mimeType": mime,
                    "data": base64.b64encode(raw).decode("utf-8"),
                }
            })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio
            }
        }
    }

    # API keys come from the environment ONLY. This list previously carried two
    # hardcoded Google/Gemini keys as trailing fallbacks, which put live
    # credentials in tracked source -- and because the literal was last in the
    # list, the service would keep working with the embedded key even if the env
    # vars were removed. Do not re-add literals here; put keys in backend/.env.
    candidate_keys = [k for k in [
        os.getenv("GEMINI_API_KEY"),
        os.getenv("GEMINI_API_KEY_BACKUP"),
        os.getenv("GOOGLE_API_KEY"),
    ] if k]

    last_error = "No keys configured"
    for key in candidate_keys:
        # The key goes in the x-goog-api-key HEADER, not the query string. Google
        # accepts both; the header form keeps the credential out of URLs, which
        # reach access logs, browser history, and any exception message that
        # embeds the request URL (a failed-call test printed a live key exactly
        # this way). Do not move it back.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            resp = requests.post(url, json=payload, timeout=45,
                                 headers={"Content-Type": "application/json",
                                          "x-goog-api-key": key})
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    cand_parts = candidates[0].get("content", {}).get("parts", [])
                    for part in cand_parts:
                        if "inlineData" in part:
                            img_bytes = base64.b64decode(part["inlineData"]["data"])
                            mime = part["inlineData"].get("mimeType", "image/png")
                        
                        if output_path:
                            out_p = Path(output_path)
                            out_p.parent.mkdir(parents=True, exist_ok=True)
                            with open(out_p, "wb") as f:
                                f.write(img_bytes)
                            return {
                                "success": True,
                                "model": model,
                                "aspect_ratio": aspect_ratio,
                                "path": str(out_p),
                                "mime_type": mime
                            }
                        return {
                            "success": True,
                            "model": model,
                            "aspect_ratio": aspect_ratio,
                            "bytes": img_bytes,
                            "mime_type": mime
                        }
                last_error = "No image candidates returned"
            else:
                last_error = f"Status {resp.status_code}: {resp.text[:300]}"
                log.warning(f"Key failed with: {last_error}, attempting next key...")
        except Exception as e:
            last_error = str(e)
            log.warning(f"Exception calling Gemini Image API: {e}")

    return {"success": False, "error": last_error}
