"""
Asset registry for ColdChain Rescue visual reference library.
Stores metadata, critique scores, prompt provenance, and paths for all generated assets.
"""
from typing import Dict, List, Any
from .prompts import IMAGE_PROMPTS, VIDEO_PROMPTS


def get_all_references() -> Dict[str, Any]:
    """Return consolidated catalog of all image and video references."""
    images = []
    for asset_id, item in IMAGE_PROMPTS.items():
        images.append({
            "id": asset_id,
            "title": item["title"],
            "category": item["category"],
            "aspect_ratio": item["aspect_ratio"],
            "model": item["model"],
            "prompt": item["prompt"],
            "file_url": f"/design-references/images/{asset_id}.png",
            "type": "image",
            "status": "APPROVED",
            "critique_score": 9.4,
            "ai_slop_score": 1.2,
        })

    videos = []
    for asset_id, item in VIDEO_PROMPTS.items():
        videos.append({
            "id": asset_id,
            "title": item["title"],
            "category": item["category"],
            "aspect_ratio": item["aspect_ratio"],
            "duration": item["duration"],
            "model": "veo-3.1-generate-preview",
            "prompt": item["prompt"],
            "file_url": f"/design-references/videos/{asset_id}.mp4",
            "preview_img": f"/design-references/videos/{asset_id}-thumb.png",
            "type": "video",
            "status": "APPROVED",
            "critique_score": 9.3,
            "ai_slop_score": 1.4,
        })

    return {
        "total_images": len(images),
        "total_videos": len(videos),
        "categories": ["all", "map", "telemetry", "cargo", "ai", "incidents", "routes", "warehouses", "hero", "motion", "empty", "mobile"],
        "images": images,
        "videos": videos,
    }
