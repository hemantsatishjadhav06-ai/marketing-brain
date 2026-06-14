// Remotion entry — register compositions here. `npx remotion studio video/index.ts`
import { Composition } from "remotion";
import { BrandReel, brandReelDefaults } from "./BrandReel";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="BrandReel"
    component={BrandReel}
    durationInFrames={150}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={brandReelDefaults}
  />
);
