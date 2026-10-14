// Standalone probe: renders CalloutChip alone on a white bg at narration frame 130
import { AbsoluteFill } from "remotion";
import { CalloutChip } from "./Demo";

export const Probe = () => {
  return (
    <AbsoluteFill style={{ background: "#ffffff" }}>
      <CalloutChip
        callout={{ label: "Digital Twin Fleet", sub: "live telemetry · thermal models", from: 100, x: 130, y: 160 }}
        narrationFrame={130}
        sceneDuration={614}
      />
    </AbsoluteFill>
  );
};
