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
    candidate_keys = [k for k in [
        os.getenv("GEMINI_API_KEY"),
        os.getenv("GEMINI_API_KEY_BACKUP"),
        os.getenv("GOOGLE_API_KEY"),
        "***REDACTED-VERTEX-SERVICE-ACCOUNT-KEY***",
        "***REDACTED-VERTEX-SERVICE-ACCOUNT-KEY***"
    ] if k]

    instance: Dict[str, Any] = {"prompt": prompt}

    # If reference image is provided, attach as image-to-video starter
    if reference_images and len(reference_images) > 0:
        first_ref = Path(reference_images[0])
        if first_ref.exists():
            try:
                with open(first_ref, "rb") as f:
                    enc = base64.b64encode(f.read()).decode("utf-8")
                mime = "image/jpeg" if first_ref.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
                instance["image"] = {
                    "bytesBase64Encoded": enc,
                    "mimeType": mime
                }
            except Exception as e:
                log.warning(f"Could not encode reference image for Veo: {e}")

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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predictLongRunning?key={key}"
        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
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

    url = f"https://generativelanguage.googleapis.com/v1beta/{operation_name}?key={GEMINI_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return {"success": False, "status_code": resp.status_code, "error": resp.text[:300]}
    except Exception as e:
        return {"success": False, "error": str(e)}
