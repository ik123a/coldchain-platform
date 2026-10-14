/**
 * Scene registry — the single source of truth for the enhanced demo timeline.
 *
 * Frame numbers are derived from the ACTUAL narration durations measured from the
 * delivered MP3s, so the enhancement stays locked to the original audio (the video
 * is a re-cut of the same recordings, not a re-take).
 */

export const FPS = 30;

export type SceneId =
  | "01_hook"
  | "02_introduce"
  | "03_fleet"
  | "04_incident"
  | "05_diagnosis"
  | "06_approval"
  | "07_execution"
  | "08_verification"
  | "09_architecture"
  | "10_quality"
  | "11_close";

export type Scene = {
  readonly id: SceneId;
  /** Narration file in public/audio */
  readonly narration: string;
  /** Recorded footage in public/clips, or null for a generated scene */
  readonly clip: string | null;
  /** Narration length in frames (measured, LEAD excluded) */
  readonly narrationFrames: number;
  /** Silent lead before narration starts, in frames */
  readonly leadFrames: number;
  /** Hold after narration ends, in frames */
  readonly tailFrames: number;
  readonly srtCue: number;
};

// LEAD = 24f (0.8s), TAIL = 21f (0.7s) — matches the original cut.
const LEAD = 24;
const TAIL = 21;

export const SCENES: readonly Scene[] = [
  {
    id: "01_hook",
    narration: "audio/01_hook.mp3",
    clip: null,
    narrationFrames: 566,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 1,
  },
  {
    id: "02_introduce",
    narration: "audio/02_introduce.mp3",
    clip: "clips/02_introduce.mp4",
    narrationFrames: 569,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 2,
  },
  {
    id: "03_fleet",
    narration: "audio/03_fleet.mp3",
    clip: "clips/03_fleet.mp4",
    narrationFrames: 536,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 3,
  },
  {
    id: "04_incident",
    narration: "audio/04_incident.mp3",
    clip: "clips/04_incident.mp4",
    narrationFrames: 544,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 4,
  },
  {
    id: "05_diagnosis",
    narration: "audio/05_diagnosis.mp3",
    clip: "clips/05_diagnosis.mp4",
    narrationFrames: 592,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 5,
  },
  {
    id: "06_approval",
    narration: "audio/06_approval.mp3",
    clip: "clips/06_approval.mp4",
    narrationFrames: 672,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 6,
  },
  {
    id: "07_execution",
    narration: "audio/07_execution.mp3",
    clip: "clips/07_execution.mp4",
    narrationFrames: 487,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 7,
  },
  {
    id: "08_verification",
    narration: "audio/08_verification.mp3",
    clip: "clips/08_verification.mp4",
    narrationFrames: 675,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 8,
  },
  {
    id: "09_architecture",
    narration: "audio/09_architecture.mp3",
    clip: null,
    narrationFrames: 688,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 9,
  },
  {
    id: "10_quality",
    narration: "audio/10_quality.mp3",
    clip: null,
    narrationFrames: 453,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 10,
  },
  {
    id: "11_close",
    narration: "audio/11_close.mp3",
    clip: "clips/11_close.mp4",
    narrationFrames: 372,
    leadFrames: LEAD,
    tailFrames: TAIL,
    srtCue: 11,
  },
];

/** Total frames for the composition (scenes butt-joined, audio lead included). */
export const TOTAL_FRAMES = SCENES.reduce(
  (sum, s) => sum + s.leadFrames + s.narrationFrames + s.tailFrames,
  0,
);

/** Absolute start frame of each scene. */
export const SCENE_STARTS: Record<SceneId, number> = SCENES.reduce(
  (acc, s) => {
    const start = SCENES.slice(0, SCENES.indexOf(s)).reduce(
      (sum, x) => sum + x.leadFrames + x.narrationFrames + x.tailFrames,
      0,
    );
    acc[s.id] = start;
    return acc;
  },
  {} as Record<SceneId, number>,
);

export const WIDTH = 1920;
export const HEIGHT = 1080;
