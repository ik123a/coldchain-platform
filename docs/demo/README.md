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

---

## Narrated version

`coldchain-rescue-demo-narrated.mp4` — same 123s video with Gemini TTS narration.

```bash
export GOOGLE_API_KEY=...          # never commit this
python make_narration.py           # one WAV per scene
python build_audio.py              # fit + mix to the video timeline
ffmpeg -i coldchain-rescue-demo.mp4 -i audiotrack/narration_track.wav \
       -c:v copy -c:a aac -b:a 192k -shortest \
       coldchain-rescue-demo-narrated.mp4
```

`make_narration.py` skips any clip that already exists, so a 429 only costs you
the scenes that failed.

### Things that will bite you

- **TTS quota is per-model, not per-key.** When `gemini-3.8-flash-tts` started
  returning 429 on two scenes, `gemini-3.8-flash-lite-tts` generated the same
  text immediately. Fall back across models instead of retrying the same one.
- **Measure scene boundaries from the video, never re-derive them from the
  recorder's sleep durations.** Hand-computing them from per-scene waits put
  every offset ~10s out. `build_audio.py` documents the pixel-fingerprint
  method that works.
- **Fit clips to their slot; do not use natural length.** `ai.wav` is 13s in an
  8.5s slot — the builder applies `atempo` (chained above 2.0x, which ffmpeg
  rejects as a single value) and caps at 1.45x so the voice stays sane.
- **Mix with `amix=normalize=0`.** The default normalises by input count, so
  narration drops to a whisper wherever clips overlap.
- **Never pad a per-clip segment.** `apad` inside each clip multiplies out
  through concat — 10 clips x 123s produced a 778s track. Pad once, at the end.
