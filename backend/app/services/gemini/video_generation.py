"""
Veo 3.1 Video Generation Service.
Implements reference video generation for ColdChain Rescue using:
- Model: veo-3.1-generate-preview (or veo-3.1-fast-generate-preview)
Supports:
- text-to-video
- image-to-video (first frame / reference guided)
- 16:9 desktop & 9:16 mobile aspect ratios
"""
import os
import time
import base64
import logging
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any

log = logging.getLogger("coldchain.gemini.video")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
DEFAULT_VIDEO_MODEL = os.getenv("GEMINI_VIDEO_MODEL", "veo-3.1-generate-preview")


def generate_reference_video(
    prompt: str,
    aspect_ratio: str = "16:9",
    duration_seconds: int = 8,
    reference_images: Optional[List[str]] = None,
    model: str = DEFAULT_VIDEO_MODEL,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Start a Veo 3.1 video generation request and poll the long-running operation.
    """
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

    instance: Dict[str, Any] = {"prompt": prompt}

    # If reference image is provided, attach as image-to-video starter.
    # Resolved through the approved-asset library — never a client-chosen path.
    # FAIL CLOSED like the image service: a refused reference must not still
    # trigger a billable Veo job with the reference silently dropped.
    if reference_images and len(reference_images) > 0:
        from .safe_paths import read_reference, ReferenceRejected
        try:
            raw, mime = read_reference(reference_images[0])
            instance["image"] = {
                "bytesBase64Encoded": base64.b64encode(raw).decode("utf-8"),
                "mimeType": mime,
            }
        except ReferenceRejected as e:
            log.warning("generation refused, reference rejected: %s", e)
            return {"success": False, "error": f"reference rejected: {e}",
                    "rejected_reference": True}

    payload = {
        "instances": [instance],
        "parameters": {
            "aspectRatio": aspect_ratio if aspect_ratio in ["16:9", "9:16"] else "16:9",
            "durationSeconds": duration_seconds,
            "sampleCount": 1
        }
    }

    last_error = "No API keys configured"
    for key in candidate_keys:
        # Key in the x-goog-api-key header, not the query string (see the image
        # service for the full rationale: URLs reach logs).
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predictLongRunning"
        try:
            resp = requests.post(url, json=payload, timeout=60,
                                 headers={"Content-Type": "application/json",
                                          "x-goog-api-key": key})
            if resp.status_code == 200:
                operation = resp.json()
                op_name = operation.get("name")
                return {
                    "success": True,
                    "operation_name": op_name,
                    "status": "QUEUED",
                    "model": model,
                    "aspect_ratio": aspect_ratio,
                    "prompt": prompt
                }
            else:
                last_error = f"Status {resp.status_code}: {resp.text[:300]}"
                log.warning(f"Veo attempt with key failed: {last_error}, trying next...")
        except Exception as e:
            last_error = str(e)
            log.warning(f"Exception calling Veo API: {e}")

    return {"success": False, "error": last_error}


def check_video_operation(operation_name: str) -> Dict[str, Any]:
    """Check the status of a Veo long-running operation."""
    if not GEMINI_API_KEY:
        return {"success": False, "error": "GEMINI_API_KEY missing"}

    # operation_name reaches a URL path. The API's format is `models/<model>/
    # operations/<id>` — anchor the check so a crafted value cannot redirect the
    # GET at an arbitrary path or query on the googleapis host (SSRF-by-parameter).
    import re as _re
    if not _re.fullmatch(r"models/[\w.\-]+/operations/[\w\-]+", operation_name or ""):
        return {"success": False, "error": "malformed operation_name"}

    url = f"https://generativelanguage.googleapis.com/v1beta/{operation_name}"
    try:
        resp = requests.get(url, timeout=15, headers={"x-goog-api-key": GEMINI_API_KEY})
        if resp.status_code == 200:
            return resp.json()
        return {"success": False, "status_code": resp.status_code, "error": resp.text[:300]}
    except Exception as e:
        return {"success": False, "error": str(e)}
