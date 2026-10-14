# ColdChain Rescue — Demo Video Production Report
**Date:** 2026-10-12 | **Deliverable:** ColdChain_Rescue_Full_Demo.mp4 (1080p30, 3:42)

## Deliverables (docs/demo/final/)
- `ColdChain_Rescue_Full_Demo.mp4` — 23.4 MB, H.264 1920x1080 30fps, AAC 48kHz stereo
- `ColdChain_Rescue_Full_Demo.srt` — 11 cues, timed to narration windows
- `SCRIPT.md` — scene-by-scene script table
- `thumbnail.png` — 1920x1080 YouTube-ready thumbnail
- `assets/` — narration MP3s (11), raw scene recordings (webm), cards, recorder scripts

## Skills installed (this production)
- **video-editing** (argus-metis/hermes-video-editing, MIT): ffmpeg/ffprobe pipelines, QC discipline
- No other video skills were needed. Duplicated-capability skills were deliberately skipped.

## Tools actually used
- **Playwright** (headless Chromium 1920x1080, 30fps) — recorded the real app with per-step DOM assertions. A shot only rolled after its preconditions (e.g. `FAILED` state, Approve button, driver console) were asserted in the DOM.
- **edge-tts** — narration (free, local)
- **ffmpeg/ffprobe** — per-scene render, concat, QC probes
- **Pillow** — title/architecture/evidence cards + thumbnail

## Honesty guardrails
- Footage is untouched real UI (no speed changes on app scenes. Cards only fade)
- Test counts verified against FINAL_ENGINEERING_AND_SECURITY_REPORT.md (138/19 — narration corrected from a wrong 143)
- No fabricated approvals, recoveries, or events. Every state shown was asserted before recording
- The isolated demo DB only. The live application DB was never touched

## Verification performed on the final MP4
- ffprobe: h264, 1920x1080, 30/1 fps, 221.67s, AAC 48000Hz stereo, 23.4 MB
- silencedetect: exactly 10 silence gaps (scene joins), each ~2.6s, none mid-scene
- blackdetect: no unintended black frames
- SRT cue 11 ends 3:40.9, inside the 3:41.7 video

## Remaining limitations
- Narration is TTS (clear Indian-English, but synthetic)
- Scene 2 recorded at the login screen rather than the marketing landing (auth gate)
- The approval click was captured on the /simulation page (the queue's real home). The map afterward shows the applied diversion
- One truck-picker screen (~7s) appears in the driver scene before the console loads
- Driver scene recorded post-repair state (the incident was already resolved in that run)
