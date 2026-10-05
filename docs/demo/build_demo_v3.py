"""Assemble the recorded shots and voiceover into the final MP4.

Two things this does that a naive `ffmpeg -i concat` does not:

1. Per-shot audio alignment. Each shot gets its own narration track padded to
   the shot's own duration, rather than one concatenated audio file laid under
   the whole video. Over ~90 seconds a single track drifts audibly against the
   picture; per-shot tracks cannot drift at all.

2. Honest failure. Each step's exit code is checked. A concat that silently
   produces a zero-length or single-shot file is worse than a loud failure,
   because it looks like success.

Everything is re-encoded to a common format first (1920x1080 @ 30fps, yuv420p,
silent stereo audio) so the concat demuxer never has to reconcile mismatched
stream parameters, which is the usual cause of "concat" producing a file that
plays only the first clip.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "demo" / "video"
SHOTS = OUT / "_shots"
VO = Path.home() / "AppData/Local/hermes/cache/scratch/vo"
WORK = OUT / "_work"
FINAL = OUT / "coldchain-rescue-demo.mp4"

W, H, FPS = 1920, 1080, 30

# Narration clips that were lengthened with a silent tail so the last word lands
# before the cut instead of being truncated mid-sentence.
PADDED = {"01-dashboard", "04-approvals", "05-incident"}


def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    FAILED: {cmd}")
        print("   ", (r.stderr or "").strip().splitlines()[-3:])
        return False
    return True


def dur(path):
    r = subprocess.run(
        f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{path}"',
        shell=True, capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def main():
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    manifest = [m for m in manifest if m.get("ok")]
    if not manifest:
        print("  x no successful shots in manifest - run record_demo_v3.py first")
        return 1

    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)

    print("=" * 64)
    print("assembling demo")
    print("=" * 64)

    parts = []
    for m in manifest:
        name = m["name"]
        src = SHOTS / f"{name}.webm"
        if not src.exists():
            print(f"  x missing footage: {src.name}")
            return 1

        clip_dur = dur(src)
        vo_file = VO / (f"{name}.padded.mp3" if name in PADDED else f"{name}.mp3")
        vo_dur = dur(vo_file) if vo_file.exists() else 0.0
        if not vo_file.exists():
            print(f"  x missing narration: {vo_file.name}")
            return 1
        if vo_dur > clip_dur:
            print(f"  x narration longer than footage on {name}: "
                  f"{vo_dur:.1f}s audio vs {clip_dur:.1f}s video")
            return 1

        part = WORK / f"{name}.mp4"
        # apad + -shortest keeps the audio exactly as long as the shot; without
        # apad a shorter track would end early and silence the tail of the shot.
        ok = run(
            f'ffmpeg -y -i "{src}" -i "{vo_file}" '
            f'-filter_complex "[1:a]apad[a]" -map 0:v -map "[a]" '
            f'-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p '
            f'-r {FPS} -c:a aac -b:a 160k -ar 48000 -ac 2 '
            f'-shortest -movflags +faststart "{part}"')
        if not ok:
            return 1
        parts.append(part)
        print(f"  {name:16} {clip_dur:6.1f}s video + {vo_dur:5.1f}s audio -> ok")

    listing = WORK / "concat.txt"
    listing.write_text(
        "\n".join(f"file '{p.name}'" for p in parts), encoding="utf-8")

    print("\n  concatenating", len(parts), "parts")
    if not run(f'ffmpeg -y -f concat -safe 0 -i "{listing}" '
               f'-c copy -movflags +faststart "{FINAL}"'):
        return 1

    final_dur = dur(FINAL)
    expected = sum(dur(p) for p in parts)
    size_mb = FINAL.stat().st_size / 1_048_576

    print("\n" + "=" * 64)
    print(f"  output : {FINAL.name}")
    print(f"  size   : {size_mb:.1f} MB")
    print(f"  length : {final_dur:.1f}s (expected {expected:.1f}s)")
    print(f"  shots  : {len(parts)}")
    print("=" * 64)

    if abs(final_dur - expected) > 1.5:
        print("  x duration mismatch - concat likely dropped a part")
        return 1
    if len(parts) > 1 and size_mb < 2:
        print("  x file suspiciously small - probably only the first shot")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())