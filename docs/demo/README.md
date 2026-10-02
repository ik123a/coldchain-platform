# Demo video

`coldchain-rescue-demo.mp4` — 2:03 walkthrough, 1600x950, H.264.

Covers all 12 screens in narrative order, with a visible cursor and a caption
per scene, plus real clicks on the live-map fleet table, the incident list and
the simulation start button. Ends on the light/dark theme toggle.

## Regenerate

Requires the backend (:8000) and frontend (:3000) both running.

```bash
cd docs/demo
python record_demo.py --rehearse   # verify selectors, no video written
python record_demo.py              # records webm
ffmpeg -i coldchain-rescue-demo.webm -c:v libx264 -crf 22 -preset medium \
       -pix_fmt yuv420p -movflags faststart coldchain-rescue-demo.mp4
```

## Gotchas found while building this

- **Python Playwright 1.62 uses flat `record_video_dir` / `record_video_size`.**
  The JS-style nested `record_video={dir,size}` raises TypeError. `slow_mo`, not
  `slowMo`.
- **Wait for the fleet before recording.** The store's first paint has
  `fleetVehicles: []`, so an immediate capture yields "Fleet: 0 units" and an
  empty table. The script polls for "14 units" first.
- **Keep the caption up for the whole scene.** Fading it right after the camera
  pan means most sampled frames have no caption.
- Injected cursor/caption elements must be re-created after every navigation.
