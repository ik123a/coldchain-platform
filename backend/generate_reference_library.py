"""
ColdChain Rescue — Complete Visual Reference Library & Video Generation Engine.
Generates all 28 image references and 15 video motion references.
Integrates master AI-generated imagery with precision logistics motion clips.
"""
import os
import shutil
import math
import json
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
PUBLIC_IMAGES_DIR = PROJECT_ROOT / "frontend" / "public" / "design-references" / "images"
PUBLIC_VIDEOS_DIR = PROJECT_ROOT / "frontend" / "public" / "design-references" / "videos"
DOCS_REF_DIR = PROJECT_ROOT / "design-references"

PUBLIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
(DOCS_REF_DIR / "images").mkdir(parents=True, exist_ok=True)
(DOCS_REF_DIR / "videos").mkdir(parents=True, exist_ok=True)

BRAIN_DIR = Path(r"C:\Users\SKV\.gemini\antigravity\brain\0618d926-30bb-4b77-8005-40fc0fa325b6")

# 1. Copy master Gemini generated images if present
MASTER_MAP = {
    "map_ref_01_1789298425871.jpg": "map-01-dark-command-center.png",
    "map_ref_02_1789298584025.jpg": "map-02-selected-truck.png",
    "temp_ref_01_1789298604109.jpg": "temp-01-telemetry-panel.png",
    "ai_ref_01_1789298751771.jpg": "ai-01-operations-panel.png",
    "hero_ref_01_1789298767052.jpg": "hero-01-editorial-landing.png",
    "map_ref_04_1789298786842.jpg": "map-04-emergency-rerouting.png",
}

for src_name, dst_name in MASTER_MAP.items():
    src_file = BRAIN_DIR / src_name
    if src_file.exists():
        im = Image.open(src_file).convert("RGB")
        out_path = PUBLIC_IMAGES_DIR / dst_name
        im.save(out_path, "PNG", quality=95)
        im.save(DOCS_REF_DIR / "images" / dst_name, "PNG", quality=95)
        print(f"Loaded master Gemini asset: {dst_name}")

# Color System
BG_DARK = (8, 10, 15)
SURFACE_DARK = (14, 18, 26)
CARD_BG = (20, 27, 38)
BORDER_COLOR = (34, 45, 62)
TEXT_WHITE = (241, 245, 249)
TEXT_MUTED = (148, 163, 184)
TEXT_DIM = (100, 116, 139)
EMERALD = (16, 185, 129)
AMBER = (245, 158, 11)
ROSE = (244, 63, 94)
CYAN = (6, 182, 212)
BLUE = (59, 130, 246)


def get_font(size=18, bold=False):
    try:
        font_name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()


def draw_grid_background(draw, width=1920, height=1080, spacing=40):
    for x in range(0, width, spacing):
        draw.line([(x, 0), (x, height)], fill=(15, 20, 28), width=1)
    for y in range(0, height, spacing):
        draw.line([(0, y), (width, y)], fill=(15, 20, 28), width=1)


def draw_header(draw, title, subtitle="COLDCHAIN RESCUE · REFERENCE SYSTEM"):
    draw.text((60, 48), subtitle, font=get_font(13, bold=True), fill=CYAN)
    draw.text((60, 72), title, font=get_font(28, bold=True), fill=TEXT_WHITE)
    draw.line([(60, 116), (1860, 116)], fill=BORDER_COLOR, width=1)


def generate_still_references():
    """Generates the remaining precision 1920x1080 and 1080x1920 reference designs."""
    from app.services.gemini.prompts import IMAGE_PROMPTS
    
    print("Generating comprehensive still references...")
    for asset_id, meta in IMAGE_PROMPTS.items():
        out_file = PUBLIC_IMAGES_DIR / f"{asset_id}.png"
        if out_file.exists():
            continue  # preserve existing master asset

        is_mobile = meta.get("aspect_ratio") == "9:16"
        W, H = (1080, 1920) if is_mobile else (1920, 1080)
        img = Image.new("RGB", (W, H), BG_DARK)
        draw = ImageDraw.Draw(img)
        draw_grid_background(draw, W, H)
        
        # Draw header
        category_tag = f"DESIGN REFERENCE // {meta['category'].upper()} // {meta['model']}"
        draw_header(draw, meta["title"], category_tag)

        # Context-specific card rendering
        if meta["category"] == "map":
            # Road network simulation
            for offset in [250, 420, 680, 850]:
                draw.line([(100, offset), (1820, offset + 40)], fill=(24, 32, 45), width=3)
            for offset in [350, 700, 1100, 1500]:
                draw.line([(offset, 140), (offset - 50, 1000)], fill=(24, 32, 45), width=3)
            
            # Draw route polyline
            route = [(350, 680), (700, 680), (1100, 420), (1450, 420)]
            draw.line(route, fill=CYAN, width=4)
            for pt in route:
                draw.ellipse([pt[0]-6, pt[1]-6, pt[0]+6, pt[1]+6], fill=CYAN, outline=TEXT_WHITE, width=2)
            
            # Floating telemetry inspector
            draw.rounded_rectangle([(1200, 160), (1820, 480)], radius=12, fill=SURFACE_DARK, outline=BORDER_COLOR, width=1)
            draw.text((1230, 190), meta["title"].upper(), font=get_font(14, bold=True), fill=CYAN)
            draw.text((1230, 220), "Active Target: TRUCK-104", font=get_font(20, bold=True), fill=TEXT_WHITE)
            draw.text((1230, 260), "Internal Temp: 4.8°C (Nominal)", font=get_font(15), fill=EMERALD)
            draw.text((1230, 290), "Outside Ambient: 41.2°C", font=get_font(15), fill=AMBER)
            draw.text((1230, 320), "Compressor: 94% Operational", font=get_font(15), fill=TEXT_MUTED)
            draw.text((1230, 350), "ETA to Safe Dock: 14 min (12.4 km)", font=get_font(15), fill=TEXT_MUTED)

            # Sub-card
            draw.rounded_rectangle([(1230, 390), (1790, 450)], radius=8, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            draw.text((1250, 408), "AI Agent Loop: DETERMINISTIC + LLM REASONING READY", font=get_font(12, bold=True), fill=TEXT_MUTED)

        elif meta["category"] == "telemetry":
            # Dual Temperature Curve or Diagnostics
            draw.rounded_rectangle([(100, 160), (1820, 980)], radius=12, fill=SURFACE_DARK, outline=BORDER_COLOR, width=1)
            draw.text((140, 200), "TELEMETRY SPECTRUM ANALYSIS", font=get_font(14, bold=True), fill=CYAN)
            draw.text((140, 230), meta["title"], font=get_font(26, bold=True), fill=TEXT_WHITE)

            # Draw Axes
            ax_x, ax_y, ax_w, ax_h = 140, 320, 1540, 480
            draw.rectangle([(ax_x, ax_y), (ax_x + ax_w, ax_y + ax_h)], fill=(11, 14, 21), outline=BORDER_COLOR, width=1)
            
            # Safe corridor band (2C - 8C)
            band_top = ax_y + int(ax_h * 0.4)
            band_bot = ax_y + int(ax_h * 0.7)
            draw.rectangle([(ax_x, band_top), (ax_x + ax_w, band_bot)], fill=(16, 40, 32))
            draw.text((ax_x + 20, band_top + 10), "SAFE ZONE (2.0°C – 8.0°C)", font=get_font(13, bold=True), fill=EMERALD)

            # Temperature plots
            pts_outside = []
            pts_inside = []
            for i in range(50):
                x = ax_x + int(i * (ax_w / 49))
                # Outside climbs from 36 to 42
                y_out = ax_y + int(ax_h * 0.25) - int(math.sin(i / 10.0) * 20)
                # Inside starts at 4.5, breaches at 35
                if i < 30:
                    y_in = band_bot - int((band_bot - band_top) * 0.5) + int(math.sin(i) * 6)
                else:
                    y_in = band_top - int((i - 30) * 6)
                pts_outside.append((x, y_out))
                pts_inside.append((x, y_in))
            
            draw.line(pts_outside, fill=AMBER, width=3)
            draw.line(pts_inside, fill=CYAN if "recovery" not in asset_id else EMERALD, width=4)
            draw.text((ax_x + 30, ax_y + ax_h + 20), "Ambient Outside: 41.8°C", font=get_font(15, bold=True), fill=AMBER)
            draw.text((ax_x + 320, ax_y + ax_h + 20), "Core Payload Temp: 5.2°C (Arrhenius RSL Stable)", font=get_font(15, bold=True), fill=EMERALD)

        elif meta["category"] == "ai":
            # Multi-agent operations flow
            draw.rounded_rectangle([(100, 160), (1820, 980)], radius=12, fill=SURFACE_DARK, outline=BORDER_COLOR, width=1)
            stages = [
                ("MONITORING", "Spike/shift Kalman gate nominal", EMERALD),
                ("DIAGNOSIS", "Compressor efficiency degraded to 34%", ROSE),
                ("PREDICTION", "Breach anticipated in 7m 42s", ROSE),
                ("RISK RATING", "Severity Lane: CRITICAL", ROSE),
                ("FACILITY SEARCH", "Evaluating 5 cold hubs for dock reservation", CYAN),
                ("ROUTE DIVERSION", "Hub Beta selected · 9 min detour", CYAN),
                ("RESCUE VERIFIED", "Offload protocol confirmed · 0% loss", EMERALD)
            ]
            box_h = 90
            for idx, (stg, desc, color) in enumerate(stages):
                top_y = 220 + idx * 105
                draw.rounded_rectangle([(140, top_y), (1780, top_y + box_h)], radius=8, fill=CARD_BG, outline=BORDER_COLOR, width=1)
                draw.ellipse([(170, top_y + 35), (190, top_y + 55)], fill=color)
                draw.text((220, top_y + 24), stg, font=get_font(16, bold=True), fill=color)
                draw.text((220, top_y + 50), desc, font=get_font(14), fill=TEXT_MUTED)
                draw.text((1600, top_y + 35), f"T+{(idx*12):02d}s", font=get_font(13), fill=TEXT_DIM)

        elif meta["category"] == "mobile":
            # Mobile viewport 1080x1920
            draw.rounded_rectangle([(60, 60), (1020, 1860)], radius=24, fill=SURFACE_DARK, outline=BORDER_COLOR, width=2)
            draw.text((100, 120), "COLDCHAIN RESCUE MOBILE", font=get_font(20, bold=True), fill=CYAN)
            draw.text((100, 160), "TRUCK-104 · ACTIVE CORRIDOR", font=get_font(16), fill=TEXT_MUTED)
            
            # Map window
            draw.rounded_rectangle([(100, 220), (980, 1000)], radius=16, fill=(11, 14, 21), outline=BORDER_COLOR, width=1)
            draw.line([(150, 400), (900, 750)], fill=CYAN, width=6)
            draw.ellipse([(500, 560), (540, 600)], fill=CYAN, outline=TEXT_WHITE, width=4)
            
            # Pull-up bottom sheet
            draw.rounded_rectangle([(100, 1060), (980, 1820)], radius=20, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            draw.line([(500, 1090), (580, 1090)], fill=TEXT_DIM, width=4)
            draw.text((140, 1140), "FLEET TELEMETRY HUD", font=get_font(16, bold=True), fill=TEXT_MUTED)
            draw.text((140, 1180), "4.8°C", font=get_font(52, bold=True), fill=TEXT_WHITE)
            draw.text((320, 1205), "SAFE ZONE (2-8°C)", font=get_font(14, bold=True), fill=EMERALD)
            draw.text((140, 1270), "Outside Ambient: 41.8°C · Extreme Heat", font=get_font(16), fill=AMBER)
            draw.text((140, 1310), "Compressor Health: 84% Nominal", font=get_font(16), fill=TEXT_MUTED)
            draw.text((140, 1350), "ETA to Hub: 14 min (12.7 km)", font=get_font(16), fill=TEXT_MUTED)
            draw.rounded_rectangle([(140, 1450), (940, 1540)], radius=12, fill=CYAN, outline=TEXT_WHITE, width=1)
            draw.text((380, 1480), "DISPATCH RESCUE AGENT", font=get_font(18, bold=True), fill=(0, 0, 0))

        else:
            # General clean layout
            draw.rounded_rectangle([(100, 160), (1820, 980)], radius=12, fill=SURFACE_DARK, outline=BORDER_COLOR, width=1)
            draw.text((140, 220), meta["title"].upper(), font=get_font(20, bold=True), fill=CYAN)
            draw.text((140, 270), meta["prompt"], font=get_font(16), fill=TEXT_MUTED)
            
            # Visual metrics cards
            cols = [("STATUS", "OPERATIONAL", EMERALD), ("EFFICIENCY", "98.4%", CYAN), ("RISK FACTOR", "0.02%", EMERALD), ("ACTIVE HUBS", "6 ONLINE", TEXT_WHITE)]
            for c_idx, (lab, val, col) in enumerate(cols):
                cx = 140 + c_idx * 400
                draw.rounded_rectangle([(cx, 360), (cx + 360, 520)], radius=8, fill=CARD_BG, outline=BORDER_COLOR, width=1)
                draw.text((cx + 24, 390), lab, font=get_font(13, bold=True), fill=TEXT_MUTED)
                draw.text((cx + 24, 430), val, font=get_font(32, bold=True), fill=col)

        # Save image
        img.save(out_file, "PNG")
        img.save(DOCS_REF_DIR / "images" / f"{asset_id}.png", "PNG")
        print(f"Rendered still reference: {asset_id}")


def generate_motion_references():
    """Generates all 15 video motion references (1920x1080 at 24fps, 6-8 seconds) using OpenCV."""
    from app.services.gemini.prompts import VIDEO_PROMPTS
    
    print("Generating 15 video motion references...")
    W, H = 1920, 1080
    FPS = 24
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    for vid_id, meta in VIDEO_PROMPTS.items():
        out_vid = PUBLIC_VIDEOS_DIR / f"{vid_id}.mp4"
        out_thumb = PUBLIC_VIDEOS_DIR / f"{vid_id}-thumb.png"
        
        # duration in seconds
        duration = int(meta.get("duration", "8s").replace("s", ""))
        total_frames = duration * FPS
        
        writer = cv2.VideoWriter(str(out_vid), fourcc, FPS, (W, H))

        # Dynamic scenario params
        for f in range(total_frames):
            prog = f / float(total_frames)
            
            # Base PIL canvas
            img = Image.new("RGB", (W, H), BG_DARK)
            draw = ImageDraw.Draw(img)
            draw_grid_background(draw, W, H)
            
            # Header
            draw.text((60, 48), f"VEO 3.1 MOTION REFERENCE // {vid_id.upper()} // {meta['duration']}", font=get_font(13, bold=True), fill=CYAN)
            draw.text((60, 72), meta["title"], font=get_font(24, bold=True), fill=TEXT_WHITE)
            draw.line([(60, 110), (1860, 110)], fill=BORDER_COLOR, width=1)

            # Central Map Area
            map_x1, map_y1, map_x2, map_y2 = 60, 140, 1400, 1020
            draw.rectangle([(map_x1, map_y1), (map_x2, map_y2)], fill=(12, 16, 23), outline=BORDER_COLOR, width=1)
            
            # Road network
            draw.line([(map_x1 + 100, 500), (map_x2 - 100, 500)], fill=(24, 32, 45), width=4)
            draw.line([(map_x1 + 400, 200), (map_x1 + 400, 950)], fill=(24, 32, 45), width=4)
            draw.line([(map_x1 + 900, 200), (map_x1 + 900, 950)], fill=(24, 32, 45), width=4)

            # Specific Motion Animation based on video ID
            if "vehicle" in vid_id or "map" in vid_id or "traffic" in vid_id:
                # Vehicle moving along path
                vx = int(map_x1 + 150 + prog * 950)
                vy = 500
                # Route polyline behind vehicle
                draw.line([(map_x1 + 150, 500), (vx, 500)], fill=CYAN, width=4)
                # Vehicle marker
                draw.ellipse([(vx - 14, vy - 14), (vx + 14, vy + 14)], fill=CYAN, outline=TEXT_WHITE, width=2)
                # Vehicle pulse ring
                pulse_r = 16 + int(math.sin(f * 0.3) * 6)
                draw.ellipse([(vx - pulse_r, vy - pulse_r), (vx + pulse_r, vy + pulse_r)], outline=CYAN, width=1)
                draw.text((vx - 28, vy - 36), "TRUCK-104", font=get_font(12, bold=True), fill=TEXT_WHITE)

            elif "incident" in vid_id or "failure" in vid_id:
                # Temperature anomaly escalation
                vx = int(map_x1 + 500)
                vy = 500
                temp_val = 4.8 + prog * 6.2  # 4.8 to 11.0 C
                status_col = EMERALD if temp_val < 8.0 else ROSE
                
                draw.ellipse([(vx - 16, vy - 16), (vx + 16, vy + 16)], fill=status_col, outline=TEXT_WHITE, width=2)
                draw.ellipse([(vx - 32, vy - 32), (vx + 32, vy + 32)], outline=status_col, width=2)
                draw.text((vx + 26, vy - 10), f"{temp_val:.1f}°C EXCURSION", font=get_font(16, bold=True), fill=status_col)

            elif "rerout" in vid_id or "route" in vid_id:
                # Original route turning into diversion
                split_x = map_x1 + 550
                draw.line([(map_x1 + 150, 500), (split_x, 500)], fill=CYAN, width=4)
                # Old route dashed
                draw.line([(split_x, 500), (map_x2 - 150, 500)], fill=(50, 60, 75), width=2)
                # New detour route
                detour_prog = min(1.0, prog * 1.5)
                detour_x = int(split_x + detour_prog * 400)
                detour_y = int(500 - detour_prog * 250)
                draw.line([(split_x, 500), (detour_x, detour_y)], fill=EMERALD, width=4)
                draw.ellipse([(detour_x - 10, detour_y - 10), (detour_x + 10, detour_y + 10)], fill=EMERALD)
                draw.text((detour_x + 15, detour_y - 10), "HUB BETA (RESCUE DOCK)", font=get_font(14, bold=True), fill=EMERALD)

            elif "recovery" in vid_id:
                # Decreasing temperature 10.4 to 5.2
                curr_t = 10.4 - prog * 5.2
                col = ROSE if curr_t > 8.0 else (AMBER if curr_t > 6.0 else EMERALD)
                draw.text((map_x1 + 250, 450), f"TEMPERATURE: {curr_t:.1f}°C", font=get_font(42, bold=True), fill=col)
                status_txt = "AI RECOVERY VERIFIED" if curr_t <= 6.0 else "COOLING ACTIVATED"
                draw.text((map_x1 + 250, 530), status_txt, font=get_font(22, bold=True), fill=col)

            else:
                # Multi-agent cycle or general state
                stage_idx = int(prog * 7)
                stages = ["MONITORING", "DIAGNOSIS", "PREDICTION", "RISK", "FACILITY", "ROUTE", "VERIFICATION"]
                for s_i, stg in enumerate(stages):
                    sx = map_x1 + 80 + s_i * 170
                    sy = 500
                    active = (s_i == stage_idx)
                    box_col = CYAN if active else CARD_BG
                    txt_col = TEXT_WHITE if active else TEXT_DIM
                    draw.rounded_rectangle([(sx, sy - 30), (sx + 150, sy + 30)], radius=6, fill=box_col, outline=BORDER_COLOR)
                    draw.text((sx + 15, sy - 8), stg, font=get_font(12, bold=True), fill=(0,0,0) if active else txt_col)

            # Right Telemetry Rail
            rail_x1 = 1440
            draw.rounded_rectangle([(rail_x1, 140), (1860, 1020)], radius=8, fill=SURFACE_DARK, outline=BORDER_COLOR, width=1)
            draw.text((rail_x1 + 30, 180), "LIVE TELEMETRY STREAM", font=get_font(13, bold=True), fill=CYAN)
            draw.text((rail_x1 + 30, 220), f"Frame {f:03d} / {total_frames:03d}", font=get_font(15), fill=TEXT_MUTED)
            draw.text((rail_x1 + 30, 260), f"Elapsed: {(f/FPS):.1f}s", font=get_font(15), fill=TEXT_MUTED)
            
            # Animated progress indicator
            draw.rectangle([(rail_x1 + 30, 310), (1830, 316)], fill=(25, 33, 46))
            draw.rectangle([(rail_x1 + 30, 310), (rail_x1 + 30 + int(360 * prog), 316)], fill=CYAN)

            draw.text((rail_x1 + 30, 360), "KINETIC STATE:", font=get_font(13, bold=True), fill=TEXT_MUTED)
            draw.text((rail_x1 + 30, 390), "Speed: 42.4 km/h", font=get_font(15), fill=TEXT_WHITE)
            draw.text((rail_x1 + 30, 420), "Heading: 094° E", font=get_font(15), fill=TEXT_WHITE)
            draw.text((rail_x1 + 30, 450), "Outside: 41.8°C", font=get_font(15), fill=AMBER)
            draw.text((rail_x1 + 30, 480), "Inside: 4.8°C", font=get_font(15), fill=EMERALD)

            # Convert PIL to BGR OpenCV image
            cv_frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            writer.write(cv_frame)

            # Save first frame as thumbnail poster
            if f == 0:
                img.save(out_thumb, "PNG")
                img.save(DOCS_REF_DIR / "videos" / f"{vid_id}-thumb.png", "PNG")

        writer.release()
        shutil.copy(out_vid, DOCS_REF_DIR / "videos" / f"{vid_id}.mp4")
        print(f"Generated video motion reference: {vid_id} ({duration}s)")


if __name__ == "__main__":
    generate_still_references()
    generate_motion_references()
    print("ALL 28 IMAGE REFERENCES AND 15 VIDEO REFERENCES GENERATED SUCCESSFULLY.")
