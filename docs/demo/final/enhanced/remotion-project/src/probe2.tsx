// Replicates the Demo scene chain: Sequence(from=611) -> narration-relative chip
import { AbsoluteFill, Sequence, useCurrentFrame } from "remotion";
import { CalloutChip } from "./Demo";

const SequenceContent: React.FC = () => {
  const f = useCurrentFrame();
  const narrationFrame = f - 24;
  return (
    <AbsoluteFill>
      <CalloutChip
        callout={{
          label: "Digital Twin Fleet",
          sub: "live telemetry · thermal models",
          from: 100,
          x: 130,
          y: 160,
        }}
        narrationFrame={narrationFrame}
        sceneDuration={614}
      />
    </AbsoluteFill>
  );
};

export const Probe2: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: "#ffffff" }}>
      <Sequence from={611} durationInFrames={614} premountFor={30}>
        <SequenceContent />
      </Sequence>
    </AbsoluteFill>
  );
};
