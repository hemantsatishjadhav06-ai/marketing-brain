// ============================================================================
// BrandReel — a Remotion composition that wears the customer's BrandSkin.
// ----------------------------------------------------------------------------
// The SAME theme tokens that skin the web cockpit drive the video, so swapping a
// brand re-skins reels with no template edits. Render headless in CI:
//
//   npx remotion render video/index.ts BrandReel out/reel.mp4 \
//     --props='{"primary":"#635BFF","title":"5 drills every beginner gets wrong"}'
//
// Install: npm i remotion @remotion/cli react react-dom
// HTML-only teams can port this 1:1 to HeyGen HyperFrames (same tokens, no React).
// ============================================================================
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, Sequence } from "remotion";
import { buildTheme, type Mode } from "../apps/web/lib/theme/brandskin";

export interface BrandReelProps {
  primary: string;
  accent?: string;
  mode?: Mode;
  brandName?: string;
  title: string;
  cta?: string;
}

export const brandReelDefaults: BrandReelProps = {
  primary: "#CCFF00",
  mode: "dark",
  brandName: "Marketing Dog",
  title: "5 drills every beginner gets wrong",
  cta: "Shop the drills →",
};

export const BrandReel: React.FC<BrandReelProps> = ({
  primary, accent, mode = "dark", brandName = "Brand", title, cta,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = buildTheme({ primary, accent })[mode];

  const enter = spring({ frame, fps, config: { damping: 200 } });
  const titleY = interpolate(enter, [0, 1], [40, 0]);
  const fadeOut = interpolate(frame, [durationInFrames - 18, durationInFrames], [1, 0], { extrapolateLeft: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: t.bg, fontFamily: "Inter, sans-serif", opacity: fadeOut }}>
      {/* brand glow */}
      <AbsoluteFill style={{ background: `radial-gradient(60% 40% at 50% 0%, ${t.accent}33, transparent 70%)` }} />

      <Sequence from={0}>
        <AbsoluteFill style={{ padding: 96, justifyContent: "space-between" }}>
          {/* wordmark */}
          <div style={{ display: "flex", alignItems: "center", gap: 16, opacity: enter }}>
            <div style={{ width: 56, height: 56, borderRadius: 16, background: t.accent }} />
            <span style={{ color: t.ink, fontSize: 34, fontWeight: 800 }}>{brandName}</span>
          </div>

          {/* headline */}
          <h1 style={{
            color: t.ink, fontSize: 104, lineHeight: 1.04, fontWeight: 800,
            transform: `translateY(${titleY}px)`, letterSpacing: -2,
          }}>
            {title}
          </h1>

          {/* CTA chip — guaranteed-legible accent button */}
          {cta && (
            <div style={{
              alignSelf: "flex-start", background: t.accent, color: t.accentInk,
              fontSize: 40, fontWeight: 700, padding: "22px 40px", borderRadius: 999,
              opacity: enter,
            }}>
              {cta}
            </div>
          )}
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};
