"""
Gemini and Veo Reference Generation & Critique API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from ...core.authz import require_auth, require_auth_read
from ...core.rate_limit import RateLimiter
from ...services.gemini.assets import get_all_references
from ...services.gemini.safe_paths import ReferenceRejected, resolve_reference
from ...services.gemini.image_generation import generate_reference_image
from ...services.gemini.video_generation import generate_reference_video, check_video_operation
from ...services.gemini.critique import critique_reference_asset
from ...services.gemini.prompts import IMAGE_PROMPTS, VIDEO_PROMPTS

router = APIRouter(prefix="/api/gemini", tags=["Gemini Design References"])

# Billable-operation limiters (D3). In-memory, single-process — the same
# documented constraint as the WS ticket store: a restart resets the counters
# and a multi-worker deployment would NOT share them. Configurable via env so a
# demo can be tightened or loosened without code changes.
_image_limiter = RateLimiter(
    per_principal=int(__import__("os").environ.get("GEMINI_RL_IMAGE_PER_MIN", 10)),
    window_s=60, name="gemini.image")
_video_limiter = RateLimiter(
    per_principal=int(__import__("os").environ.get("GEMINI_RL_VIDEO_PER_MIN", 3)),
    window_s=60, name="gemini.video")
_critique_limiter = RateLimiter(
    per_principal=int(__import__("os").environ.get("GEMINI_RL_CRITIQUE_PER_MIN", 15)),
    window_s=60, name="gemini.critique")


class ImageGenRequest(BaseModel):
    # Bounded so a caller cannot post an unbounded prompt to a billable model.
    prompt: str = Field(min_length=1, max_length=4000)
    aspect_ratio: str = "16:9"
    model: str = "gemini-3.1-flash-image"
    # Asset ids / bare filenames from the approved library — NOT filesystem paths.
    reference_images: Optional[List[str]] = Field(default=None, max_length=3)


class VideoGenRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    aspect_ratio: str = "16:9"
    # Video is the more expensive call; cap the requested length.
    duration_seconds: int = Field(default=8, ge=1, le=30)
    reference_images: Optional[List[str]] = Field(default=None, max_length=1)
    model: str = "veo-3.1-generate-preview"


class CritiqueRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=4000)


def _validate_references(refs: Optional[List[str]]) -> None:
    """Reject a bad reference with 400 BEFORE any billable upstream call.

    Validating in the route (not only in the service) matters: if the service
    silently skipped a bad reference and generated anyway, a rejected request
    would still spend money. A refused request must cost nothing.
    """
    if not refs:
        return
    for ref in refs:
        try:
            resolve_reference(ref)
        except ReferenceRejected as e:
            raise HTTPException(400, f"invalid reference image: {e}")


@router.get("/references")
async def list_references(_auth: dict = Depends(require_auth_read)):
    """List all registered visual reference assets, videos, prompts, and scores."""
    return get_all_references()


@router.post("/generate-image")
async def api_generate_image(req: ImageGenRequest, claims: dict = Depends(require_auth)):
    """Generate reference image via Gemini 3.1 Flash Image or 3 Pro Image."""
    principal = str(claims.get("email") or claims.get("sub") or "?")
    if not _image_limiter.allow(principal):
        raise HTTPException(429, "image generation rate limit exceeded; try later")
    _validate_references(req.reference_images)
    res = generate_reference_image(
        prompt=req.prompt,
        aspect_ratio=req.aspect_ratio,
        model=req.model,
        reference_images=req.reference_images,
    )
    return res


@router.post("/generate-video")
async def api_generate_video(req: VideoGenRequest, claims: dict = Depends(require_auth)):
    """Queue Veo 3.1 video generation."""
    principal = str(claims.get("email") or claims.get("sub") or "?")
    if not _video_limiter.allow(principal):
        raise HTTPException(429, "video generation rate limit exceeded; try later")
    _validate_references(req.reference_images)
    res = generate_reference_video(
        prompt=req.prompt,
        aspect_ratio=req.aspect_ratio,
        duration_seconds=req.duration_seconds,
        reference_images=req.reference_images,
        model=req.model,
    )
    return res


@router.get("/video-status/{operation_name:path}")
async def api_video_status(operation_name: str, _auth: dict = Depends(require_auth_read)):
    """Poll Veo 3.1 operation status."""
    return check_video_operation(operation_name)


@router.post("/critique")
async def api_critique(req: CritiqueRequest, claims: dict = Depends(require_auth)):
    """Run automated Anti-AI-Slop design critique with Gemini reasoning model."""
    principal = str(claims.get("email") or claims.get("sub") or "?")
    if not _critique_limiter.allow(principal):
        raise HTTPException(429, "critique rate limit exceeded; try later")
    res = critique_reference_asset(
        asset_id=req.asset_id,
        title=req.title,
        category=req.category,
        prompt=req.prompt,
    )
    # Honest failure mapping: the three statuses are distinguishable client-side.
    if res.get("success") is False:
        status = res.get("status", "failed")
        if status == "unavailable":
            raise HTTPException(503, res["error"])
        if status == "rate_limited":
            raise HTTPException(429, res["error"])
        raise HTTPException(502, res["error"])
    return res
