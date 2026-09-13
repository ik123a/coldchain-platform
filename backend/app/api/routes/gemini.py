"""
Gemini and Veo Reference Generation & Critique API endpoints.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from ...services.gemini.assets import get_all_references
from ...services.gemini.image_generation import generate_reference_image
from ...services.gemini.video_generation import generate_reference_video, check_video_operation
from ...services.gemini.critique import critique_reference_asset
from ...services.gemini.prompts import IMAGE_PROMPTS, VIDEO_PROMPTS

router = APIRouter(prefix="/api/gemini", tags=["Gemini Design References"])


class ImageGenRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"
    model: str = "gemini-3.1-flash-image"
    reference_images: Optional[List[str]] = None


class VideoGenRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "16:9"
    duration_seconds: int = 8
    reference_images: Optional[List[str]] = None
    model: str = "veo-3.1-generate-preview"


class CritiqueRequest(BaseModel):
    asset_id: str
    title: str
    category: str
    prompt: str


@router.get("/references")
async def list_references():
    """List all registered visual reference assets, videos, prompts, and scores."""
    return get_all_references()


@router.post("/generate-image")
async def api_generate_image(req: ImageGenRequest):
    """Generate reference image via Gemini 3.1 Flash Image or 3 Pro Image."""
    res = generate_reference_image(
        prompt=req.prompt,
        aspect_ratio=req.aspect_ratio,
        model=req.model,
        reference_images=req.reference_images,
    )
    return res


@router.post("/generate-video")
async def api_generate_video(req: VideoGenRequest):
    """Queue Veo 3.1 video generation."""
    res = generate_reference_video(
        prompt=req.prompt,
        aspect_ratio=req.aspect_ratio,
        duration_seconds=req.duration_seconds,
        reference_images=req.reference_images,
        model=req.model,
    )
    return res


@router.get("/video-status/{operation_name:path}")
async def api_video_status(operation_name: str):
    """Poll Veo 3.1 operation status."""
    return check_video_operation(operation_name)


@router.post("/critique")
async def api_critique(req: CritiqueRequest):
    """Run automated Anti-AI-Slop design critique with Gemini reasoning model."""
    res = critique_reference_asset(
        asset_id=req.asset_id,
        title=req.title,
        category=req.category,
        prompt=req.prompt,
    )
    return res
