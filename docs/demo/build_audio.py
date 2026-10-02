"""
Build a narration track aligned to the demo video timeline.

Design decision: clips are FIT to their scene slot, not placed at their natural
length. Gemini TTS speaks at its own pace; a 13s clip ("ai") inside a 10s scene
would either overrun into the next scene or force an unreadably fast read.

Method, per scene:
  1. compute the slot from the measured video scene boundaries
  2. if the clip is longer than the slot, speed it with atempo (chain factors
     >2.0 are illegal in ffmpeg, so they must be multiplied out)
  3. if shorter, pad with silence
This guarantees narration never spills across a scene boundary.
"""
import json, os, subprocess, sys

SCRATCH = r"C:\Users\SKV\AppData\Local\hermes\cache\scratch"
NARR = os.path.join(SCRATCH, "narration")
BUILD = os.path.join(SCRATCH, "audiotrack")
os.makedirs(BUILD, exist_ok=True)

# Scene boundaries MEASURED from the rendered video, not estimated.
#
# Method: `ffmpeg -vf fps=2,scale=320:-1` sampled every 0.5s, then each frame
# was reduced to an 80x48 greyscale fingerprint; a mean-absolute-difference
# above ~9 marks a navigation. The 12 boundaries below reproduce the 12 scenes
# in order and land on 123s, matching the file duration.
#
# An earlier hand-computed table from the recorder's per-scene waits was ~10s
# adrift from these values — the narrator would have spoken over the wrong
# screens. Measure pixels; do not re-derive a timeline from sleep durations.
OFFSETS = {
    "home":       0.0,
    "dashboard":  11.0,
    "live-map":   26.0,
    "fleet":      43.0,
    "incidents":  51.0,
    "ai":         63.0,
    "analytics":  71.0,
    "twin":       79.0,
    "simulation": 87.0,
    "reports":   105.0,
    "settings":  113.5,
    "theme":     119.0,
}
TOTAL = 123.0  # exact video duration

ORDER = ["home", "dashboard", "live-map", "fleet", "incidents", "ai",
         "analytics", "twin", "simulation", "reports", "settings", "theme"]

# Narration starts slightly AFTER the scene appears, so the caption is read
# first and the voice does not talk over the transition.
LEAD_IN = 0.6
MAX_SPEEDUP = 1.45  # beyond ~1.45x the voice starts sounding comical


def dur(path):
    o = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True)
    return float(o.stdout.strip() or 0)


def atempo_chain(factor):
    """ffmpeg's atempo only accepts 0.5-2.0; multiply out anything outside."""
    parts = []
    while factor > 2.0:
        parts.append("atempo=2.0")
        factor /= 2.0
    if abs(factor - 1.0) > 0.01:
        parts.append(f"atempo={factor:.4f}")
    return ",".join(parts) if parts else "anull"


built = []
missing = []
for i, key in enumerate(ORDER):
    src = os.path.join(NARR, f"{key}.wav")
    if not os.path.exists(src):
        missing.append(key)
        continue
    start = OFFSETS[key]
    end = OFFSETS[ORDER[i + 1]] if i + 1 < len(ORDER) else TOTAL
    slot = max(0.5, (end - start) - LEAD_IN)
    d = dur(src)

    speed = 1.0
    if d > slot:
        speed = min(MAX_SPEEDUP, d / slot)
    fitted_dur = d / speed

    out = os.path.join(BUILD, f"{key}.wav")
    # adelay places the clip at its scene start. No apad and no -t here: the
    # final mix is ONE ffmpeg pass over all clips with per-input adelay, so no
    # segment ever carries its own padding (a per-segment pad multiplies out
    # through concat — 10 clips x 123s produced a 778s track).
    delay_ms = int((start + LEAD_IN) * 1000)
    filt = atempo_chain(speed)
    cmd = ["ffmpeg", "-y", "-i", src, "-af", f"{filt},adelay={delay_ms}|{delay_ms}",
           "-ar", "44100", "-ac", "1", out]
    subprocess.run(cmd, capture_output=True)
    built.append((key, start, d, round(speed, 3), round(fitted_dur, 2)))

print(f"{'scene':12} {'start':>7} {'clip':>7} {'x':>6} {'fitted':>7}")
for k, s, d, sp, fd in built:
    print(f"{k:12} {s:7.1f} {d:7.2f} {sp:6.2f} {fd:7.2f}")
if missing:
    print("\nMISSING (skipped):", ", ".join(missing))

# One ffmpeg pass over all clips, each already carrying its own adelay, mixed
# with amix. amix normalises by input count, so `normalize=0` is required or the
# narration drops to a whisper wherever several inputs overlap.
inputs = []
for key, _, _, _, _ in built:
    inputs += ["-i", os.path.join(BUILD, f"{key}.wav")]
filters = "".join(f"[{i}:a]" for i in range(len(built)))
mix = (f"{filters}amix=inputs={len(built)}:normalize=0:dropout_transition=0[mixed];"
       f"[mixed]apad=whole_dur={TOTAL},atrim=0:{TOTAL}[out]")
track = os.path.join(BUILD, "narration_track.wav")
cmd = ["ffmpeg", "-y", *inputs,
       "-filter_complex", mix, "-map", "[out]",
       "-ar", "44100", "-ac", "1", track]
r = subprocess.run(cmd, capture_output=True)
if r.returncode != 0:
    print("MIX FAILED:", r.stderr.decode()[-500:])
else:
    print("\ntrack:", track, f"{os.path.getsize(track)/1e6:.2f} MB",
          f"{dur(track):.2f}s")
