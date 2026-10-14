import React from "react";
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { SCENES, SCENE_STARTS, TOTAL_FRAMES, type SceneId } from "./scenes";

// Absolute scene-start frames in order (skip the first — no whoosh at t=0).
const SCENE_STARTS_ARR = SCENES.map((s) => SCENE_STARTS[s.id]);

/**
 * Demo — the enhanced ColdChain Rescue cut.
 *
 * Re-uses the delivered narration and the recorded footage, and adds:
 *   - UI zoom / focus on the live map while telemetry climbs
 *   - animated mouse pointer + click indicator on the approval card
 *   - animated logistics route with service-truck dispatch
 *   - architecture + test-evidence cards
 *   - synchronized captions (parsed from the delivered SRT)
 *   - cross-fade transitions between scenes
 */

// Plain props type — no zod schema (Remotion infers props from defaultProps).
export type DemoProps = {
  showCaptions: boolean;
  showOverlays: boolean;
  showIndicators: boolean;
};

// ---------------------------------------------------------------------------
// Scene-only window (each sequence runs in scene-local frames)
// ---------------------------------------------------------------------------

const Scene: React.FC<{
  index: number;
  children: (localFrame: number, duration: number) => React.ReactNode;
}> = ({ index, children }) => {
  const scene = SCENES[index];
  const start = SCENE_STARTS[scene.id];
  return (
    <Sequence
      from={start}
      durationInFrames={scene.leadFrames + scene.narrationFrames + scene.tailFrames}
      name={scene.id}
      premountFor={30}
    >
      <SceneInner sceneIndex={index}>{children}</SceneInner>
    </Sequence>
  );
};

const SceneInner: React.FC<{
  sceneIndex: number;
  children: (localFrame: number, duration: number) => React.ReactNode;
}> = ({ sceneIndex, children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const scene = SCENES[sceneIndex];
  // Subtract the lead so narration-relative overlays (e.g. the pointer) line up
  // with the spoken words.
  const narrationFrame = frame - scene.leadFrames;
  return <AbsoluteFill>{children(narrationFrame, durationInFrames)}</AbsoluteFill>;
};

// ---------------------------------------------------------------------------
// Per-scene feature callouts, timed to the narration phrases (narration-relative
// frames; scene narration windows: 02:569f, 03:536f, 04:544f, 05:592f, 06:672f,
// 07:487f, 08:675f).
// ---------------------------------------------------------------------------

const CALLOUTS: Partial<Record<SceneId, readonly Callout[]>> = {
  "02_introduce": [
    { label: "Digital Twin Fleet", sub: "live telemetry · thermal models", from: 100, x: 130, y: 160 },
    { label: "Deterministic Rescue Agents", sub: "no LLM in the decision path", from: 330, x: 1180, y: 620 },
    { label: "Human-in-the-Loop", sub: "every critical move approved", from: 470, x: 560, y: 700 },
  ],
  "03_fleet": [
    { label: "Live Fleet Map", sub: "position · cargo temp · state", from: 60, x: 130, y: 150 },
    { label: "Per-Truck Thermal Model", sub: "projects load behavior", from: 330, x: 1120, y: 780 },
  ],
  "04_incident": [
    { label: "Genuine Fault Injection", sub: "compressor failure → twin", from: 90, x: 1100, y: 170 },
    { label: "FAILED", sub: "compressor reports failed", from: 260, x: 1290, y: 560 },
    { label: "Temperature Rising", sub: "cargo band breached soon", from: 400, x: 170, y: 720 },
  ],
  "05_diagnosis": [
    { label: "Top-6 Root Causes", sub: "scored by the expert system", from: 70, x: 950, y: 180 },
    { label: "Evidence on Screen", sub: "compressor state · temp slope", from: 300, x: 180, y: 640 },
    { label: "100% Traceable", sub: "rule-based, not a black box", from: 460, x: 1150, y: 800 },
  ],
  "06_approval": [
    { label: "Facility Scoring", sub: "travel · dock queue · capacity · cost", from: 70, x: 140, y: 160 },
    { label: "Autonomy Stops", sub: "asks the human operator", from: 300, x: 1150, y: 240 },
    { label: "Operator Approves", sub: "recommendation + reasoning", from: 500, x: 520, y: 700 },
  ],
  "07_execution": [
    { label: "Route Diversion Applied", sub: "twin updated live", from: 60, x: 130, y: 160 },
    { label: "Service Truck Dispatched", sub: "drives → repairs → done", from: 220, x: 1080, y: 640 },
  ],
  "08_verification": [
    { label: "Recovery Verification", sub: "cargo checked vs band", from: 90, x: 1000, y: 170 },
    { label: "Recorded Evidence", sub: "before an incident closes", from: 300, x: 170, y: 660 },
    { label: "Honest Analytics", sub: "fixes ≠ verified recoveries", from: 480, x: 1120, y: 800 },
  ],
};

// ---------------------------------------------------------------------------
// Demo
// ---------------------------------------------------------------------------

export const Demo: React.FC<DemoProps> = ({
  showCaptions,
  showOverlays,
  showIndicators,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0d1422" }}>
      {/* --- 01 hook: title card --- */}
      <Scene index={0}>
        {(f, d) => (
          <FleetTitleCard localFrame={f} duration={d} showOverlays={showOverlays} />
        )}
      </Scene>

      {/* --- 02 introduce: landing/login footage --- */}
      <Scene index={1}>
        {(f, d) => (
          <FootageScene
            localFrame={f}
            duration={d}
            clip="clips/02_introduce.mp4"
            callouts={CALLOUTS["02_introduce"]}
          />
        )}
      </Scene>

      {/* --- 03 fleet: live map (slow drift + zoom) --- */}
      <Scene index={2}>
        {(f, d) => (
          <FootageScene
            localFrame={f}
            duration={d}
            clip="clips/03_fleet.mp4"
            callouts={CALLOUTS["03_fleet"]}
          />
        )}
      </Scene>

      {/* --- 04 incident: zoom into the failing truck row --- */}
      <Scene index={3}>
        {(f, d) => (
          <FootageScene
            localFrame={f}
            duration={d}
            clip="clips/04_incident.mp4"
            zoom={{ from: 1.0, to: 1.35, startFrac: 0.25, endFrac: 0.95 }}
            callouts={CALLOUTS["04_incident"]}
          />
        )}
      </Scene>

      {/* --- 05 diagnosis: incidents panel --- */}
      <Scene index={4}>
        {(f, d) => (
          <FootageScene
            localFrame={f}
            duration={d}
            clip="clips/05_diagnosis.mp4"
            callouts={CALLOUTS["05_diagnosis"]}
          />
        )}
      </Scene>

      {/* --- 06 approval: pointer + click indicator on Approve --- */}
      <Scene index={5}>
        {(f, d) => (
          <FootageScene
            localFrame={f}
            duration={d}
            clip="clips/06_approval.mp4"
            zoom={{ from: 1.05, to: 1.25, startFrac: 0.1, endFrac: 0.7 }}
            zoomOrigin={{ x: 0.28, y: 0.88 }}
            showIndicators={showIndicators}
            callouts={CALLOUTS["06_approval"]}
          />
        )}
      </Scene>

      {/* --- 07 execution: service truck route animation over the map --- */}
      <Scene index={6}>
        {(f, d) => (
          <FootageScene
            localFrame={f}
            duration={d}
            clip="clips/07_execution.mp4"
            zoom={{ from: 1.0, to: 1.08, startFrac: 0.2, endFrac: 0.85 }}
            callouts={CALLOUTS["07_execution"]}
          />
        )}
      </Scene>

      {/* --- 08 verification: analytics --- */}
      <Scene index={7}>
        {(f, d) => (
          <FootageScene
            localFrame={f}
            duration={d}
            clip="clips/08_verification.mp4"
            callouts={CALLOUTS["08_verification"]}
          />
        )}
      </Scene>

      {/* --- 09 architecture: diagram card --- */}
      <Scene index={8}>
        {(f, d) => (
          <ArchitectureCard localFrame={f} duration={d} showOverlays={showOverlays} />
        )}
      </Scene>

      {/* --- 10 quality: test-evidence card --- */}
      <Scene index={9}>
        {(f, d) => <EvidenceCard localFrame={f} duration={d} />}
      </Scene>

      {/* --- 11 close: title card --- */}
      <Scene index={10}>
        {(f, d) => (
          <FleetTitleCard localFrame={f} duration={d} showOverlays={showOverlays} closing />
        )}
      </Scene>

      {/* --- narration: every scene, in original order --- */}
      {SCENES.map((s) => (
        <Sequence
          key={s.id}
          from={SCENE_STARTS[s.id]}
          durationInFrames={s.leadFrames + s.narrationFrames + s.tailFrames}
          name={`audio-${s.id}`}
        >
          <Audio src={staticFile(s.narration)} />
        </Sequence>
      ))}

      {/* --- sound design: ambient bed + transitions + hits ---------------- */}
      {/* Ambient pad under everything, ducked 4dB, trimmed to video length */}
      <Sequence  durationInFrames={TOTAL_FRAMES} name="sfx-pad" premountFor={30}>
        <Audio src={staticFile("audio/ambient_pad.wav")} volume={(f) =>
          // fade in 1s, fade out 2s at the end
          f < 30 ? f / 30 : f > TOTAL_FRAMES - 60 ? (TOTAL_FRAMES - f) / 60 : 0.55
        } />
      </Sequence>

      {/* Whoosh at every scene boundary (transition energy) */}
      {SCENE_STARTS_ARR.slice(1).map((start) => (
        <Sequence key={`wh-${start}`} from={start - 12} durationInFrames={30} name={`sfx-whoosh-${start}`}>
          <Audio src={staticFile("audio/whoosh.wav")} volume={0.5} />
        </Sequence>
      ))}

      {/* Riser into the approval scene (the "stop and ask a human" beat) */}
      <Sequence from={SCENE_STARTS["06_approval"] - 24} durationInFrames={60} name="sfx-riser">
        <Audio src={staticFile("audio/riser.wav")} volume={0.55} />
      </Sequence>

      {/* Click when the operator approves (mid approval scene) */}
      <Sequence from={SCENE_STARTS["06_approval"] + 24 + 540} durationInFrames={30} name="sfx-click">
        <Audio src={staticFile("audio/click.wav")} volume={0.9} />
      </Sequence>

      {/* Success chime when the recovery verifies (mid verification scene) */}
      <Sequence from={SCENE_STARTS["08_verification"] + 24 + 420} durationInFrames={40} name="sfx-chime">
        <Audio src={staticFile("audio/chime.wav")} volume={0.6} />
      </Sequence>

      {/* --- synchronized captions --- */}
      {showCaptions ? <CaptionsLayer /> : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Footage scene with optional zoom, route overlay, and click indicators
// ---------------------------------------------------------------------------

const FootageScene: React.FC<{
  localFrame: number;
  duration: number;
  clip: string;
  zoom?: { from: number; to: number; startFrac: number; endFrac: number };
  zoomOrigin?: { x: number; y: number };
  showIndicators?: boolean;
  showRoute?: boolean;
  callouts?: readonly Callout[];
}> = ({
  localFrame,
  duration,
  clip,
  zoom,
  zoomOrigin = { x: 0.5, y: 0.5 },
  showIndicators,
  showRoute,
  callouts,
}) => {
  const { width, height } = useVideoConfig();
  const scale = zoom
    ? lerpClamped(localFrame, zoom.startFrac * duration, zoom.endFrac * duration, zoom.from, zoom.to)
    : 1;

  const cx = zoomOrigin.x * width;
  const cy = zoomOrigin.y * height;

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          transform: `scale(${scale})`,
          transformOrigin: `${zoomOrigin.x * 100}% ${zoomOrigin.y * 100}%`,
        }}
      >
        <OffthreadVideo
          src={staticFile(clip)}
          muted
          playbackRate={1}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>

      {showRoute ? (
        <RouteOverlay localFrame={localFrame} duration={duration} />
      ) : null}

      {callouts
        ? callouts.map((c) => (
            <CalloutChip
              key={c.label}
              callout={c}
              narrationFrame={localFrame}
              sceneDuration={duration}
            />
          ))
        : null}

      {showIndicators ? (
        <ClickIndicator
          localFrame={localFrame}
          duration={duration}
          targetX={cx}
          targetY={cy}
        />
      ) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Route overlay — animated logistics path with service-truck dispatch
// ---------------------------------------------------------------------------

const RouteOverlay: React.FC<{
  localFrame: number;
  duration: number;
}> = ({ localFrame, duration }) => {
  const { width, height } = useVideoConfig();
  const progress = clamp01((localFrame - duration * 0.15) / (duration * 0.7));
  // Route: from the failing truck (map centre-left) to the rescue facility
  const p0 = { x: width * 0.32, y: height * 0.55 };
  const p1 = { x: width * 0.5, y: height * 0.35 };
  const p2 = { x: width * 0.68, y: height * 0.42 };

  // Cumulative arc length fraction for the two segments (quadratic bezier)
  const t = progress;
  const pt = (t: number) => {
    const u = 1 - t;
    return {
      x: u * u * p0.x + 2 * u * t * p1.x + t * t * p2.x,
      y: u * u * p0.y + 2 * u * t * p1.y + t * t * p2.y,
    };
  };
  const head = pt(t);
  const path = `M ${p0.x} ${p0.y} Q ${p1.x} ${p1.y} ${p2.x} ${p2.y}`;

  return (
    <AbsoluteFill>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <path
          d={path}
          fill="none"
          stroke="rgba(96,205,255,0.35)"
          strokeWidth={6}
          strokeDasharray="14 12"
        />
        <path
          d={path}
          fill="none"
          stroke="#60cdff"
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={`${progress * 1000} 1000`}
        />
        {/* origin marker */}
        <circle cx={p0.x} cy={p0.y} r={12} fill="#ff6b6b" />
        <circle cx={p0.x} cy={p0.y} r={22} fill="none" stroke="#ff6b6b" strokeWidth={2} opacity={0.6} />
        {/* destination marker */}
        <circle cx={p2.x} cy={p2.y} r={12} fill="#4ade80" />
        {/* service truck */}
        <g transform={`translate(${head.x}, ${head.y})`}>
          <circle r={20} fill="#0d1422" stroke="#60cdff" strokeWidth={3} />
          <text
            x={0}
            y={7}
            textAnchor="middle"
            fill="#60cdff"
            fontSize={22}
            fontFamily="Segoe UI, Arial"
            fontWeight={700}
          >
            ❄
          </text>
        </g>
      </svg>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Click indicator — LCU-style organic cursor glide, parking, and spring click
// Synced precisely to frame 540 (sfx-click and "the operator approves")
// ---------------------------------------------------------------------------

const ClickIndicator: React.FC<{
  localFrame: number;
  duration: number;
  targetX: number;
  targetY: number;
}> = ({ localFrame, duration, targetX, targetY }) => {
  // Narration-relative milestones:
  // - 460f: cursor enters from off-center top-right
  // - 520f: cursor parks at target (decelerates to rest)
  // - 540f: operator clicks (matches sfx-click at frame 540)
  // - 540-620f: expanding ripples + verified approval confirmation chip
  const enterStart = 460;
  const parkFrame = 520;
  const clickAt = 540;

  // Bezier trajectory calculation
  const travelT = clamp01((localFrame - enterStart) / (parkFrame - enterStart));
  const easeTravel = Math.sin((travelT * Math.PI) / 2); // organic ease-out curve

  const startX = targetX + 380;
  const startY = targetY - 280;
  const midX = targetX + 160;
  const midY = targetY - 240;

  // Quadratic bezier position
  const u = 1 - easeTravel;
  const curX = u * u * startX + 2 * u * easeTravel * midX + easeTravel * easeTravel * targetX;
  const curY = u * u * startY + 2 * u * easeTravel * midY + easeTravel * easeTravel * targetY;

  // Cursor physical squash on click (motionmaxxing law: 2-3f squash, 1f target answer)
  const clickT = localFrame - clickAt;
  const isClicking = clickT >= 0 && clickT <= 6;
  const cursorScale = travelT < 1
    ? 1.25 - 0.25 * easeTravel // oversize arrival settles to 1.0
    : isClicking
      ? 0.86 // physical press squash
      : 1.0;

  // Click ripple dynamics
  const clicked = clickT >= 0 && clickT < 65;
  const rippleT = clamp01(clickT / 65);
  const ringRadius = 16 + rippleT * 68;
  const ringOpacity = 1 - rippleT;

  // Confirmation chip spring animation
  const chipPop = smoothstep(clickAt + 2, clickAt + 14, localFrame);

  if (localFrame < enterStart) return null;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Target focus hover glow while cursor is parked (frames 520-540) */}
      {localFrame >= parkFrame && localFrame < clickAt ? (
        <div
          style={{
            position: "absolute",
            left: targetX - 55,
            top: targetY - 24,
            width: 110,
            height: 48,
            borderRadius: 8,
            border: "1.5px solid rgba(96,205,255,0.7)",
            boxShadow: "0 0 16px rgba(96,205,255,0.35)",
            opacity: 0.6 + 0.4 * Math.sin((localFrame - parkFrame) * 0.35),
          }}
        />
      ) : null}

      {/* Primary expanding click ripple ring */}
      {clicked ? (
        <>
          <div
            style={{
              position: "absolute",
              left: targetX - ringRadius,
              top: targetY - ringRadius,
              width: ringRadius * 2,
              height: ringRadius * 2,
              borderRadius: "50%",
              border: "3px solid #10b981",
              boxShadow: "0 0 20px rgba(16,185,129,0.7)",
              opacity: ringOpacity,
            }}
          />
          <div
            style={{
              position: "absolute",
              left: targetX - ringRadius * 0.65,
              top: targetY - ringRadius * 0.65,
              width: ringRadius * 1.3,
              height: ringRadius * 1.3,
              borderRadius: "50%",
              border: "1.5px solid #60cdff",
              opacity: ringOpacity * 0.8,
            }}
          />
        </>
      ) : null}

      {/* Precision cursor pointer */}
      <svg
        width={40}
        height={40}
        viewBox="0 0 24 24"
        style={{
          position: "absolute",
          left: curX,
          top: curY,
          transform: `scale(${cursorScale})`,
          transformOrigin: "top left",
          filter: "drop-shadow(0 4px 10px rgba(0,0,0,0.75))",
          zIndex: 100,
        }}
      >
        <path
          d="M5 3 L5 19 L9.5 15 L12.5 21 L15.5 19.5 L12.5 14 L18 13 Z"
          fill="#ffffff"
          stroke="#0a0a0b"
          strokeWidth={1.8}
        />
      </svg>

      {/* Verified human approval confirmation chip */}
      {clickT >= 2 ? (
        <div
          style={{
            position: "absolute",
            left: targetX + 38,
            top: targetY + 28,
            padding: "8px 18px",
            borderRadius: 8,
            background: "rgba(18,28,45,0.95)",
            border: "1.5px solid #10b981",
            boxShadow: "0 4px 20px rgba(0,0,0,0.6), 0 0 16px rgba(16,185,129,0.35)",
            color: "#4ade80",
            fontFamily: "Segoe UI, Arial, sans-serif",
            fontSize: 20,
            fontWeight: 700,
            letterSpacing: 1.2,
            opacity: chipPop,
            transform: `scale(${0.88 + 0.12 * chipPop})`,
            zIndex: 90,
          }}
        >
          ✓ APPROVED · DISPATCHING RESCUE
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// SaaS-style feature callouts (reference: leadjet/viable demo style) —
// a chip pops in when the narration names the feature, holds, fades out.
// Coordinates are in screen space (callouts ride ABOVE the zoomed footage).
// ---------------------------------------------------------------------------

type Callout = {
  readonly label: string;
  /** Narration-relative frame when the chip pops in */
  readonly from: number;
  /** Screen position (top-left of chip) */
  readonly x: number;
  readonly y: number;
  /** Optional second line */
  readonly sub?: string;
  /** Visible length in frames (default 150) */
  readonly hold?: number;
};

const CALLOUT_HOLD = 150;

export const CalloutChip: React.FC<{
  callout: Callout;
  narrationFrame: number;
  sceneDuration: number;
}> = ({ callout, narrationFrame, sceneDuration }) => {
  const { from, x, y, sub, hold = CALLOUT_HOLD } = callout;
  const local = narrationFrame - from;
  if (local < 0 || local > hold) {
    return null;
  }
  const popIn = smoothstep(0, 16, local);
  const fadeOut = 1 - smoothstep(hold - 18, hold, local);
  const sceneEndGuard = 1 - smoothstep(sceneDuration - 8, sceneDuration, narrationFrame);
  const opacity = popIn * fadeOut * sceneEndGuard;
  const scale = 0.72 + 0.28 * popIn;
  const rise = (1 - popIn) * 14;
  const pulse = 0.5 + 0.5 * Math.sin(narrationFrame / 4.5);

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y + rise,
        opacity,
        transform: `scale(${scale})`,
        transformOrigin: "left center",
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "16px 26px 16px 20px",
        borderRadius: 14,
        background: "rgba(10,15,26,0.97)",
        border: "2px solid rgba(96,205,255,0.7)",
        boxShadow: "0 12px 40px rgba(0,0,0,0.75), 0 0 0 1px rgba(0,0,0,0.5)",
      }}
    >
      <div
        style={{
          width: 12,
          height: 12,
          borderRadius: 6,
          background: "#60cdff",
          boxShadow: `0 0 ${6 + pulse * 10}px rgba(96,205,255,${0.6 + pulse * 0.4})`,
          flexShrink: 0,
        }}
      />
      <div>
        <div
          style={{
            fontFamily: "Segoe UI, Arial",
            fontSize: 27,
            fontWeight: 700,
            color: "#eef4fb",
            whiteSpace: "nowrap",
          }}
        >
          {callout.label}
        </div>
        {sub ? (
          <div
            style={{
              fontFamily: "Segoe UI, Arial",
              fontSize: 20,
              fontWeight: 500,
              color: "#9fb2cc",
              marginTop: 3,
              whiteSpace: "nowrap",
            }}
          >
            {sub}
          </div>
        ) : null}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Count-up number (evidence card)
// ---------------------------------------------------------------------------

const CountUp: React.FC<{
  to: number;
  startF: number;
  localFrame: number;
  frames?: number;
  suffix?: string;
}> = ({ to, startF, localFrame, frames = 45, suffix }) => {
  const t = clamp01((localFrame - startF) / frames);
  const eased = 1 - Math.pow(1 - t, 3);
  const value = Math.round(to * eased);
  const pop = smoothstep(0, 12, localFrame - startF);
  return (
    <span
      style={{
        display: "inline-block",
        opacity: pop,
        transform: `scale(${0.85 + 0.15 * pop})`,
        transformOrigin: "left center",
      }}
    >
      {value}
      {suffix ?? ""}
    </span>
  );
};

// ---------------------------------------------------------------------------
// Title cards (hook + close)
// ---------------------------------------------------------------------------

const FleetTitleCard: React.FC<{
  localFrame: number;
  duration: number;
  showOverlays: boolean;
  closing?: boolean;
}> = ({ localFrame, duration, showOverlays, closing }) => {
  const t = clamp01(localFrame / (duration * 0.5));
  const fadeIn = smoothstep(0, 30, localFrame);
  const fadeOut = 1 - smoothstep(duration - 30, duration, localFrame);
  const rise = (1 - t) * 60;

  return (
    <AbsoluteFill
      style={{
        background: "radial-gradient(1200px 700px at 70% 20%, #1b2c48 0%, #0d1422 60%)",
        opacity: fadeIn * fadeOut,
        fontFamily: "Segoe UI, Arial",
      }}
    >
      {/* frost particles */}
      {showOverlays
        ? Array.from({ length: 26 }).map((_, i) => {
            const seed = i * 37.13;
            const x = (seed * 13.7) % 100;
            const speed = 0.25 + ((i * 19) % 60) / 100;
            const y = ((localFrame * speed + seed * 7) % (duration + 200)) - 100;
            const size = 2 + (i % 4);
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: `${x}%`,
                  top: y,
                  width: size,
                  height: size,
                  borderRadius: "50%",
                  background: "rgba(150,220,255,0.55)",
                }}
              />
            );
          })
        : null}

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            transform: `translateY(${rise}px)`,
            textAlign: "center",
            color: "#e8eef6",
          }}
        >
          <div style={{ fontSize: 108, fontWeight: 800, letterSpacing: 4 }}>
            {"COLDCHAIN RESCUE".split(" ").map((word, wi) => (
              <span key={wi} style={{ display: "inline-block", whiteSpace: "pre" }}>
                {word.split("").map((ch, ci) => {
                  const charIdx = wi === 0 ? ci : "COLDCHAIN ".length + ci;
                  const appear = smoothstep(6 + charIdx * 3, 20 + charIdx * 3, localFrame);
                  return (
                    <span
                      key={ci}
                      style={{
                        display: "inline-block",
                        opacity: appear,
                        transform: `translateY(${(1 - appear) * 36}px)`,
                      }}
                    >
                      {ch}
                    </span>
                  );
                })}
                {wi === 0 ? " " : ""}
              </span>
            ))}
          </div>
          <div
            style={{
              fontSize: 44,
              fontWeight: 600,
              color: "#60cdff",
              marginTop: 26,
              opacity: smoothstep(40, 60, localFrame),
              transform: `translateY(${(1 - smoothstep(40, 60, localFrame)) * 24}px)`,
            }}
          >
            {closing
              ? "Autonomy that proposes. Humans that approve."
              : "A digital twin for refrigerated logistics"}
          </div>
          {!closing ? (
            <div
              style={{
                fontSize: 34,
                color: "#96a3b8",
                marginTop: 34,
                letterSpacing: 2,
                opacity: smoothstep(60, 84, localFrame),
              }}
            >
              DETECT · DIAGNOSE · PROPOSE · APPROVE · EXECUTE · VERIFY
            </div>
          ) : (
            <div
              style={{
                marginTop: 60,
                display: "flex",
                justifyContent: "center",
                gap: 18,
                opacity: smoothstep(30, 55, localFrame),
              }}
            >
              {["Next.js", "FastAPI", "Deterministic Agents", "Human Approval"].map(
                (chip, i) => (
                  <div
                    key={chip}
                    style={{
                      padding: "14px 30px",
                      borderRadius: 40,
                      border: "1.5px solid rgba(96,205,255,0.5)",
                      background: "rgba(22,35,58,0.85)",
                      fontSize: 26,
                      fontWeight: 600,
                      color: "#bcd8ef",
                      opacity: smoothstep(30 + i * 8, 48 + i * 8, localFrame),
                    }}
                  >
                    {chip}
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Architecture diagram card
// ---------------------------------------------------------------------------

const ArchitectureCard: React.FC<{
  localFrame: number;
  duration: number;
  showOverlays: boolean;
}> = ({ localFrame, duration }) => {
  const fade = smoothstep(0, 20, localFrame) * (1 - smoothstep(duration - 20, duration, localFrame));
  const nodes = [
    { label: "Next.js Front End", sub: "dashboard · live map · analytics", x: 130, y: 250, key: "fe" },
    { label: "FastAPI Backend", sub: "REST + authenticated WebSocket", x: 750, y: 250, key: "be" },
    { label: "SQLite Store", sub: "fleet · incidents · routes", x: 1370, y: 250, key: "db" },
    { label: "Driver Console", sub: "role-scoped UI", x: 130, y: 560, key: "drv" },
    { label: "Simulation Core", sub: "deterministic Python agents", x: 750, y: 560, key: "sim" },
    { label: "Auth Layer", sub: "server-side roles · single-use tickets", x: 1370, y: 560, key: "auth" },
  ];

  return (
    <AbsoluteFill
      style={{
        background: "radial-gradient(1100px 650px at 20% 10%, #16233a 0%, #0d1422 65%)",
        opacity: fade,
        fontFamily: "Segoe UI, Arial",
        color: "#e8eef6",
      }}
    >
      <div style={{ position: "absolute", left: 130, top: 90, fontSize: 34, fontWeight: 700, color: "#60cdff", letterSpacing: 3 }}>
        ARCHITECTURE
      </div>
      <svg width={1920} height={1080}>
        <line x1={690} y1={340} x2={750} y2={340} stroke="#60cdff" strokeWidth={3} />
        <line x1={1310} y1={340} x2={1370} y2={340} stroke="#60cdff" strokeWidth={3} />
        <line x1={690} y1={650} x2={750} y2={650} stroke="#3c4d69" strokeWidth={3} />
        <line x1={1310} y1={650} x2={1370} y2={650} stroke="#3c4d69" strokeWidth={3} />
        <line x1={1030} y1={460} x2={1030} y2={560} stroke="#60cdff" strokeWidth={3} />
      </svg>
      {nodes.map((n, i) => {
        const delay = i * 8;
        const pop = smoothstep(delay, delay + 18, localFrame);
        return (
          <div
            key={n.key}
            style={{
              position: "absolute",
              left: n.x,
              top: n.y,
              width: 560,
              height: 180,
              borderRadius: 18,
              background: "#162032",
              border: "1px solid #3c4d69",
              padding: "28px 30px",
              boxSizing: "border-box",
              transform: `scale(${0.9 + 0.1 * pop})`,
              opacity: pop,
            }}
          >
            <div style={{ fontSize: 32, fontWeight: 700 }}>{n.label}</div>
            <div style={{ fontSize: 24, color: "#96a3b8", marginTop: 14 }}>{n.sub}</div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Test-evidence card
// ---------------------------------------------------------------------------

const EvidenceCard: React.FC<{
  localFrame: number;
  duration: number;
}> = ({ localFrame, duration }) => {
  const fade = smoothstep(0, 20, localFrame) * (1 - smoothstep(duration - 20, duration, localFrame));
  const rows = [
    { big: 143, label: "backend tests, database-isolated (100% pass)", startF: 30, suffix: "" },
    { big: 19, label: "acceptance-sweep assertions", startF: 80, suffix: "/19" },
    { big: 0, label: "live-DB writes across all test runs", startF: 130, suffix: "" },
    { big: 17, label: "production routes, 100% type-safe", startF: 180, suffix: "/17" },
  ];
  return (
    <AbsoluteFill
      style={{
        background: "radial-gradient(1100px 650px at 80% 30%, #16233a 0%, #0d1422 65%)",
        fontFamily: "Segoe UI, Arial",
        color: "#e8eef6",
        opacity: fade,
      }}
    >
      <div style={{ position: "absolute", left: 140, top: 90, fontSize: 34, fontWeight: 700, color: "#60cdff", letterSpacing: 3 }}>
        VERIFIED, NOT CLAIMED
      </div>
      {rows.map((r, i) => (
        <div key={r.label} style={{ position: "absolute", left: 360, top: 230 + i * 135 }}>
          <span style={{ fontSize: 74, fontWeight: 800, color: "#60cdff", display: "inline-block", minWidth: 160 }}>
            <CountUp to={r.big} startF={r.startF} localFrame={localFrame} suffix={r.suffix} />
          </span>
          <span style={{ fontSize: 34, fontWeight: 600, marginLeft: 24 }}>{r.label}</span>
        </div>
      ))}
      <div style={{ position: "absolute", left: 0, right: 0, top: 800, textAlign: "center", fontSize: 26, color: "#96a3b8" }}>
        Honest failure paths — no faked approvals, no invented recoveries, 100% test integrity
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Captions — parsed from the delivered SRT, displayed at the bottom
// ---------------------------------------------------------------------------

const CaptionsLayer: React.FC = () => {
  const [captions, setCaptions] = React.useState<Array<{ startMs: number; endMs: number; text: string }> | null>(null);

  React.useEffect(() => {
    fetch(staticFile("captions/demo.srt"))
      .then((r) => r.text())
      .then((text) => {
        setCaptions(parseSrtSimple(text));
      })
      .catch(() => setCaptions([]));
  }, []);

  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const nowMs = (frame / fps) * 1000;

  const active = captions?.find((c) => nowMs >= c.startMs && nowMs <= c.endMs);

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "flex-end", paddingRight: 70, pointerEvents: "none" }}>
      {active ? (
        <div
          style={{
            marginBottom: 26,
            maxWidth: 1160,
            padding: "12px 28px",
            borderRadius: 12,
            background: "rgba(10,16,28,0.92)",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "#ffffff",
            fontSize: 30,
            lineHeight: 1.3,
            fontFamily: "Segoe UI, Arial, sans-serif",
            textAlign: "right",
            boxShadow: "0 8px 26px rgba(0,0,0,0.7)",
            zIndex: 80,
          }}
        >
          {active.text}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function parseSrtSimple(text: string): Array<{ startMs: number; endMs: number; text: string }> {
  const out: Array<{ startMs: number; endMs: number; text: string }> = [];
  const blocks = text.split(/\r?\n\r?\n/);
  for (const b of blocks) {
    const m = b.match(
      /(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/,
    );
    if (!m) continue;
    const startMs =
      (((+m[1] * 60 + +m[2]) * 60 + +m[3]) * 1000) + +m[4];
    const endMs =
      (((+m[5] * 60 + +m[6]) * 60 + +m[7]) * 1000) + +m[8];
    const lines = b.split(/\r?\n/);
    const textLine = lines.slice(2).join(" ").trim();
    if (textLine) out.push({ startMs, endMs, text: textLine });
  }
  return out;
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = clamp01((x - edge0) / Math.max(1e-6, edge1 - edge0));
  return t * t * (3 - 2 * t);
}

/** Interpolate with clamping outside the window. */
function lerpClamped(frame: number, fromFrame: number, toFrame: number, a: number, b: number): number {
  const t = smoothstep(fromFrame, toFrame, frame);
  return a + (b - a) * t;
}
