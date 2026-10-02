"""
Generate narration audio for the ColdChain Rescue demo video.

One WAV per scene, then a script to concatenate them into a single track aligned
to the video timeline. Split per-scene because:
  - Veo/TTS quota is finite; a failed scene retries alone
  - each scene's text can be tuned without regenerating the others
  - output stays inspectable per scene
"""
import os, json, base64, time, urllib.request, sys

KEY = os.environ["GOOGLE_API_KEY"]
OUT = r"C:\Users\SKV\AppData\Local\hermes\cache\scratch\narration"
os.makedirs(OUT, exist_ok=True)

MODEL = "gemini-3.8-flash-tts"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"

# Voice: Kore is a warm, measured female voice - suits an explainer rather than
# a hype read. Puck/Charon/Kore/Fenrir are the documented options.
VOICE = "Kore"

# (scene key, on-screen caption, narration text)
# Keep each ~1 sentence: a caption bar already names the screen, so the voice
# should add what the screen CANNOT show.
SCENES = [
    ("home",
     "ColdChain Rescue - AI cold-chain command center",
     "This is ColdChain Rescue. Fourteen refrigerated trucks are being monitored in real time, "
     "and the platform decides how to save cargo before a cold chain breaks."),

    ("dashboard",
     "Operations dashboard - live fleet KPIs and map",
     "The dashboard is the operations centre. Live counts, a telemetry feed, and every truck on the map. "
     "Anything at risk surfaces here first."),

    ("live-map",
     "Live Map - 14 digital twins on the Delhi-NCR corridor",
     "The live map shows all fourteen digital twins. Each marker is colour-coded by risk, "
     "and clicking one opens its full telemetry and cargo state."),

    ("fleet",
     "Fleet table - filter by state, click any truck",
     "The fleet table lets an operator filter by state and inspect any vehicle, "
     "including driver score and remaining route."),

    ("incidents",
     "Incidents - root cause, actions, recovery evidence",
     "Every incident is auditable. The root cause, the confidence behind it, "
     "the actions taken, and the evidence that the recovery actually worked."),

    ("ai",
     "AI Command - the deterministic agent chain",
     "This is the part that matters. The decision chain runs on deterministic rules, "
     "not a language model. The same input always produces the same rescue plan, "
     "which is why the system can be audited and defended."),

    ("analytics",
     "Analytics - fleet-level performance",
     "Analytics aggregates fleet performance over time: interventions, recoveries, "
     "violations, and route deviations."),

    ("twin",
     "Digital Twin - full internal vehicle state",
     "The digital twin exposes a vehicle's full internal state, "
     "which is what makes the simulation a twin rather than a map marker."),

    ("simulation",
     "Simulation - inject failures, replay incidents",
     "Any fault can be injected on demand, and a recorded incident can be replayed tick by tick. "
     "That is how the system is demonstrated without waiting for a real breakdown."),

    ("reports",
     "Reports - export incident JSON or PDF",
     "Incidents export as JSON or PDF for the record."),

    ("settings",
     "Settings - theme, AI mode, cargo profiles",
     "Settings controls appearance, the AI mode, and the cargo temperature profiles "
     "that define what counts as a breach."),

    ("theme",
     "Light and dark themes - one click, persists after reload",
     "The interface ships in both a light and a dark theme. "
     "The light theme swaps the map basemap too, and the choice persists after reload."),
]


def synth(text, voice=VOICE, retries=3):
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                URL, data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
            for p in d["candidates"][0]["content"]["parts"]:
                if "inlineData" in p:
                    return base64.b64decode(p["inlineData"]["data"])
            raise RuntimeError("no audio part in response")
        except Exception as e:
            code = getattr(e, "code", None)
            msg = str(e)[:120]
            print(f"    attempt {attempt} failed: {msg}")
            if code == 400:
                raise  # a bad voice name or malformed body won't fix itself
            time.sleep(3 * attempt)
    raise RuntimeError("TTS failed after retries")


if __name__ == "__main__":
    only = sys.argv[1:] or None
    manifest = {}
    for key, caption, text in SCENES:
        if only and key not in only:
            continue
        path = os.path.join(OUT, f"{key}.wav")
        if os.path.exists(path) and os.path.getsize(path) > 10000:
            print(f"[skip] {key} already exists")
            continue
        print(f"[tts] {key}: {text[:58]}...")
        try:
            audio = synth(text)
            with open(path, "wb") as f:
                f.write(audio)
            print(f"  -> {len(audio)//1024} KB")
            manifest[key] = len(audio)
        except Exception as e:
            print(f"  FAILED {key}: {e}")
    print("\ndone:", len(manifest), "clips generated")
