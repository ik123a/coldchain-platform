import { Composition } from "remotion";
import { Demo } from "./Demo";
import { Probe } from "./probe";
import { Probe2 } from "./probe2";
import { FPS, HEIGHT, TOTAL_FRAMES, WIDTH } from "./scenes";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Demo"
        component={Demo}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{
          showCaptions: true,
          showOverlays: true,
          showIndicators: true,
        }}
      />
  <Composition id="Probe2" component={Probe2} durationInFrames={900} fps={30} width={1920} height={1080} />
      <Composition id="Probe" component={Probe} durationInFrames={1} fps={30} width={1920} height={1080} />
    </>
  );
};
