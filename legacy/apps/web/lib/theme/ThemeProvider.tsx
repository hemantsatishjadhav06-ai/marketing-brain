"use client";
// ThemeProvider — applies a BrandSkin theme as CSS custom properties on <html>.
// Portable (only depends on React + ./brandskin). Drop into apps/web.
//
// Usage (apps/web/app/layout.tsx):
//   <ThemeProvider initialBrand={{ primary: org.accent_color }}>{children}</ThemeProvider>
// Anywhere below:  const { brand, setBrand, mode, setMode, theme } = useBrandTheme();

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import {
  buildTheme, themeToCssVars, type BrandInput, type BrandTheme, type Mode,
} from "./brandskin";

interface Ctx {
  brand: BrandInput;
  setBrand: (b: BrandInput) => void;
  mode: Mode;
  setMode: (m: Mode) => void;
  toggleMode: () => void;
  theme: BrandTheme;
}

const ThemeCtx = createContext<Ctx | null>(null);
const LS_BRAND = "md_brand";
const LS_MODE = "md_mode";
const DEFAULT_BRAND: BrandInput = { primary: "#CCFF00" };

function applyVars(vars: Record<string, string>) {
  const root = document.documentElement;
  for (const [k, v] of Object.entries(vars)) root.style.setProperty(k, v);
}

export function ThemeProvider({
  children,
  initialBrand,
  initialMode = "dark",
}: {
  children: ReactNode;
  initialBrand?: BrandInput;
  initialMode?: Mode;
}) {
  const [brand, setBrandState] = useState<BrandInput>(initialBrand ?? DEFAULT_BRAND);
  const [mode, setModeState] = useState<Mode>(initialMode);

  const theme = useMemo(() => buildTheme(brand), [brand]);

  // hydrate persisted choices + OS colour-scheme + reduced motion
  useEffect(() => {
    try {
      const b = localStorage.getItem(LS_BRAND);
      if (b) setBrandState(JSON.parse(b));
      const m = localStorage.getItem(LS_MODE) as Mode | null;
      if (m) setModeState(m);
      else if (window.matchMedia?.("(prefers-color-scheme: light)").matches) setModeState("light");
    } catch { /* ignore */ }
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      document.documentElement.setAttribute("data-reduced-motion", "true");
    }
  }, []);

  // apply tokens whenever theme or mode changes
  useEffect(() => {
    applyVars(themeToCssVars(theme[mode]));
    document.documentElement.dataset.mode = mode;
    document.documentElement.style.colorScheme = mode;
  }, [theme, mode]);

  const setBrand = useCallback((b: BrandInput) => {
    setBrandState(b);
    try { localStorage.setItem(LS_BRAND, JSON.stringify(b)); } catch { /* ignore */ }
  }, []);
  const setMode = useCallback((m: Mode) => {
    setModeState(m);
    try { localStorage.setItem(LS_MODE, m); } catch { /* ignore */ }
  }, []);
  const toggleMode = useCallback(() => setMode(mode === "dark" ? "light" : "dark"), [mode, setMode]);

  const value = useMemo<Ctx>(
    () => ({ brand, setBrand, mode, setMode, toggleMode, theme }),
    [brand, setBrand, mode, setMode, toggleMode, theme],
  );

  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}

export function useBrandTheme(): Ctx {
  const ctx = useContext(ThemeCtx);
  if (!ctx) throw new Error("useBrandTheme must be used inside <ThemeProvider>");
  return ctx;
}

// Optional: render server-side to avoid a first-paint flash. Inject the result
// into <html style={...}> in a Server Component using the org's saved colour.
export function initialThemeStyle(brand: BrandInput, mode: Mode = "dark"): Record<string, string> {
  return themeToCssVars(buildTheme(brand)[mode]);
}
