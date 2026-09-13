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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

    # Build prompt parts
    parts: List[Dict[str, Any]] = [{"text": prompt}]

    # If reference images provided, encode and attach for multi-reference consistency
    if reference_images:
        for ref_path in reference_images[:3]:
            p = Path(ref_path)
            if p.exists():
                try:
                    with open(p, "rb") as f:
                        enc = base64.b64encode(f.read()).decode("utf-8")
                    mime = "image/jpeg" if p.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
                    parts.append({
                        "inlineData": {
                            "mimeType": mime,
                            "data": enc
                        }
                    })
                except Exception as e:
                    log.warning(f"Could not read reference image {ref_path}: {e}")

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": aspect_ratio
            }
        }
    }

    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=45)
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
            return {"success": False, "error": "No image candidates returned", "raw": data}
        else:
            return {
                "success": False,
                "status_code": resp.status_code,
                "error": resp.text[:500]
            }
    except Exception as e:
        log.exception(f"Error calling Gemini Image API: {e}")
        return {"success": False, "error": str(e)}
