// ============================================================================
// BrandSkin — Marketing Dog's adaptive theming engine (typed)
// ----------------------------------------------------------------------------
// Framework-free, dependency-free. Mirrors engine/brandskin.mjs exactly so the
// product, the standalone demo, and the test-suite all share one source of math.
// Every text/UI token is forced through `ensureContrast`, so a theme is WCAG-AA
// by construction regardless of how extreme the brand colour is.
// ============================================================================

export interface RGB { r: number; g: number; b: number; }
export interface OKLCH { L: number; C: number; h: number; }

export interface Tokens {
  bg: string; bg2: string; panel: string; panel2: string; line: string;
  ink: string; ink2: string; mute: string;
  accent: string; accentInk: string;
  good: string; warn: string; danger: string;
}
export interface BrandTheme {
  name: string;
  seed: { primary: string; accent: string };
  ramp: Record<string, string>;
  light: Tokens;
  dark: Tokens;
}
export interface BrandInput { primary: string; accent?: string; name?: string; }
export type Mode = "light" | "dark";

export const clamp01 = (x: number): number => (x < 0 ? 0 : x > 1 ? 1 : x);
const clamp = (x: number, lo: number, hi: number): number => (x < lo ? lo : x > hi ? hi : x);

export function hexToRgb(hex: string): RGB {
  let h = String(hex).trim().replace(/^#/, "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const n = parseInt(h, 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}
export function rgbToHex({ r, g, b }: RGB): string {
  const to = (v: number) => Math.round(clamp(v, 0, 255)).toString(16).padStart(2, "0");
  return "#" + to(r) + to(g) + to(b);
}

const srgbToLin = (c: number): number => {
  c /= 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
};
const linToSrgb = (c: number): number => {
  const v = c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
  return clamp01(v) * 255;
};

export function relLuminance(rgb: RGB | string): number {
  const c = typeof rgb === "string" ? hexToRgb(rgb) : rgb;
  return 0.2126 * srgbToLin(c.r) + 0.7152 * srgbToLin(c.g) + 0.0722 * srgbToLin(c.b);
}
/** WCAG 2.x contrast ratio in [1, 21]. */
export function contrast(a: RGB | string, b: RGB | string): number {
  const L1 = relLuminance(a), L2 = relLuminance(b);
  const hi = Math.max(L1, L2), lo = Math.min(L1, L2);
  return (hi + 0.05) / (lo + 0.05);
}
export function bestForeground(bgHex: string): string {
  return contrast("#ffffff", bgHex) >= contrast("#000000", bgHex) ? "#ffffff" : "#000000";
}

function rgbToOklab({ r, g, b }: RGB): { L: number; a: number; b: number } {
  const lr = srgbToLin(r), lg = srgbToLin(g), lb = srgbToLin(b);
  const l = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb;
  const m = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb;
  const s = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb;
  const l_ = Math.cbrt(l), m_ = Math.cbrt(m), s_ = Math.cbrt(s);
  return {
    L: 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
    a: 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
    b: 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
  };
}
function oklabToRgb({ L, a, b }: { L: number; a: number; b: number }): RGB {
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.2914855480 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  return {
    r: linToSrgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    g: linToSrgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    b: linToSrgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s),
  };
}
export function rgbToOklch(rgb: RGB): OKLCH {
  const { L, a, b } = rgbToOklab(rgb);
  return { L, C: Math.hypot(a, b), h: Math.atan2(b, a) };
}
export const hexToOklch = (hex: string): OKLCH => rgbToOklch(hexToRgb(hex));
export const oklchToHex = (o: OKLCH): string =>
  rgbToHex(oklabToRgb({ L: o.L, a: o.C * Math.cos(o.h), b: o.C * Math.sin(o.h) }));

export function withLightness(hex: string, L: number, chromaScale = 1): string {
  const o = hexToOklch(hex);
  return oklchToHex({ L: clamp01(L), C: o.C * chromaScale, h: o.h });
}

/** Nudge `fg` (in OKLCH, tapering chroma) until it clears `target` contrast vs `bg`. */
export function ensureContrast(fgHex: string, bgHex: string, target: number): string {
  if (contrast(fgHex, bgHex) >= target) return fgHex;
  const dir = relLuminance(bgHex) < 0.5 ? +1 : -1;
  const o = hexToOklch(fgHex);
  let best = fgHex, bestC = contrast(fgHex, bgHex);
  for (let i = 1; i <= 120; i++) {
    const t = i / 120;
    const L = clamp01(o.L + dir * t);
    const cand = oklchToHex({ L, C: o.C * Math.max(0.15, 1 - t * 0.7), h: o.h });
    const c = contrast(cand, bgHex);
    if (c > bestC) { bestC = c; best = cand; }
    if (c >= target) return cand;
  }
  const bw = bestForeground(bgHex);
  return contrast(bw, bgHex) > bestC ? bw : best;
}

const RAMP_STOPS: Record<string, number> = {
  "50": 0.972, "100": 0.93, "200": 0.86, "300": 0.78, "400": 0.70,
  "500": 0.62, "600": 0.545, "700": 0.47, "800": 0.39, "900": 0.31, "950": 0.235,
};
export function ramp(seedHex: string): Record<string, string> {
  const o = hexToOklch(seedHex);
  const out: Record<string, string> = {};
  for (const k of Object.keys(RAMP_STOPS)) {
    const L = RAMP_STOPS[k];
    const taper = 1 - Math.abs(L - 0.62) / 0.62;
    out[k] = oklchToHex({ L, C: o.C * (0.5 + 0.5 * taper), h: o.h });
  }
  return out;
}

export function buildTheme(input: BrandInput): BrandTheme {
  const primary = input.primary;
  const accent = input.accent || primary;
  const ph = hexToOklch(primary).h;
  const neutral = (L: number, C = 0.008) => oklchToHex({ L, C, h: ph });

  const dBg = neutral(0.16, 0.012);
  let dAccent = withLightness(accent, Math.max(0.74, hexToOklch(accent).L));
  dAccent = ensureContrast(dAccent, dBg, 3.0);
  const dark: Tokens = {
    bg: dBg, bg2: neutral(0.195, 0.012), panel: neutral(0.215, 0.014),
    panel2: neutral(0.255, 0.014), line: neutral(0.315, 0.01),
    ink: ensureContrast(neutral(0.965, 0.004), dBg, 7.0),
    ink2: ensureContrast(neutral(0.86, 0.006), dBg, 4.5),
    mute: ensureContrast(neutral(0.7, 0.012), dBg, 4.5),
    accent: dAccent, accentInk: ensureContrast(bestForeground(dAccent), dAccent, 4.5),
    good: ensureContrast("#34d399", dBg, 3.0),
    warn: ensureContrast("#fbbf24", dBg, 3.0),
    danger: ensureContrast("#fb7185", dBg, 3.0),
  };

  const lBg = neutral(0.99, 0.004);
  let lAccent = withLightness(accent, Math.min(0.56, hexToOklch(accent).L));
  lAccent = ensureContrast(lAccent, lBg, 3.0);
  const light: Tokens = {
    bg: lBg, bg2: neutral(0.972, 0.005), panel: "#ffffff",
    panel2: neutral(0.965, 0.006), line: neutral(0.9, 0.012),
    ink: ensureContrast(neutral(0.24, 0.02), lBg, 7.0),
    ink2: ensureContrast(neutral(0.4, 0.02), lBg, 4.5),
    mute: ensureContrast(neutral(0.52, 0.02), lBg, 4.5),
    accent: lAccent, accentInk: ensureContrast(bestForeground(lAccent), lAccent, 4.5),
    good: ensureContrast("#15803d", lBg, 3.0),
    warn: ensureContrast("#b45309", lBg, 3.0),
    danger: ensureContrast("#dc2626", lBg, 3.0),
  };

  return { name: input.name || "Brand", seed: { primary, accent }, ramp: ramp(primary), light, dark };
}

export function themeToCssVars(t: Tokens): Record<string, string> {
  return {
    "--bg": t.bg, "--bg-2": t.bg2, "--panel": t.panel, "--panel-2": t.panel2,
    "--line": t.line, "--ink": t.ink, "--ink-2": t.ink2, "--mute": t.mute,
    "--accent": t.accent, "--accent-ink": t.accentInk,
    "--good": t.good, "--warn": t.warn, "--danger": t.danger,
  };
}

export interface AuditRow { name: string; ratio: number; min: number; pass: boolean; }
export function auditTheme(t: Tokens): { pass: boolean; rows: AuditRow[] } {
  const checks: Array<[string, string, string, number]> = [
    ["ink / bg", t.ink, t.bg, 7.0],
    ["ink2 / bg", t.ink2, t.bg, 4.5],
    ["mute / bg", t.mute, t.bg, 4.5],
    ["ink / panel", t.ink, t.panel, 4.5],
    ["accent / bg", t.accent, t.bg, 3.0],
    ["accentInk / accent", t.accentInk, t.accent, 4.5],
    ["good / bg", t.good, t.bg, 3.0],
    ["danger / bg", t.danger, t.bg, 3.0],
  ];
  const rows: AuditRow[] = checks.map(([name, fg, bg, min]) => {
    const ratio = Math.round(contrast(fg, bg) * 100) / 100;
    return { name, ratio, min, pass: ratio >= min };
  });
  return { pass: rows.every((r) => r.pass), rows };
}

export const PRESET_BRANDS: BrandInput[] = [
  { name: "Tennis Neon", primary: "#CCFF00" },
  { name: "Padel Cyan", primary: "#22D3EE" },
  { name: "Stripe Indigo", primary: "#635BFF" },
  { name: "Spotify Green", primary: "#1DB954" },
  { name: "Coca-Cola Red", primary: "#F40009" },
  { name: "Barbie Pink", primary: "#E0218A" },
  { name: "IKEA", primary: "#0058A3", accent: "#FFDB00" },
  { name: "Slack Aubergine", primary: "#4A154B", accent: "#36C5F0" },
  { name: "McDonald's", primary: "#FFC72C", accent: "#DA291C" },
  { name: "Midnight Mono", primary: "#0A0A0A" },
];
