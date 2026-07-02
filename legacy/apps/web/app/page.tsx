"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";
import { useBrandTheme } from "@/lib/theme/ThemeProvider";
import { PRESET_BRANDS, auditTheme } from "@/lib/theme/brandskin";

const FEATURES = [
  { i: "🎨", t: "BrandSkin™ theming", d: "Your whole cockpit wears your brand — derived from your real colours, auto-corrected to stay WCAG-AA legible." },
  { i: "🧠", t: "A real brand brain", d: "Voice, tone, banned phrases, CTAs, SEO terms, competitors — a living memory every agent reads before it writes." },
  { i: "🚧", t: "Brand-safe by force", d: "A three-layer guard means content never bleeds across verticals or off-voice. The Critic gates every draft." },
  { i: "📅", t: "Self-filling calendar", d: "A 30-day plan that builds itself to your cadence — every slot carries the AI reason it's there." },
  { i: "📡", t: "Native publishing", d: "Instagram, YouTube, TikTok, X, LinkedIn, Pinterest, Klaviyo — or export a clean bundle." },
  { i: "🎬", t: "On-brand video", d: "Remotion + HyperFrames render reels that read the same brand tokens. Swap brand, re-skin the video." },
];

export default function Landing() {
  const { mode, setMode, brand, setBrand, theme } = useBrandTheme();
  const [hasSession, setHasSession] = useState(false);
  useEffect(() => { setHasSession(!!getToken()); }, []);
  const audit = auditTheme(theme[mode]);

  return (
    <div className="relative bg-aurora min-h-screen overflow-hidden">
      <div className="noise absolute inset-0" aria-hidden="true" />
      <div className="relative">
        {/* nav */}
        <header className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="size-7 rounded-lg accent-bg grid place-items-center" aria-hidden="true">🐾</span>
            <span className="display text-lg">Marketing Dog</span>
          </Link>
          <nav className="hidden md:flex items-center gap-7 text-sm text-mute" aria-label="Primary">
            <a href="#how" className="hover:text-ink">How it works</a>
            <a href="#features" className="hover:text-ink">Features</a>
            <a href="#skin" className="hover:text-ink">BrandSkin</a>
          </nav>
          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-xl border hairline bg-panel p-1" role="group" aria-label="Colour mode">
              {(["dark", "light"] as const).map((m) => (
                <button key={m} onClick={() => setMode(m)} aria-pressed={mode === m}
                  className={"px-2.5 py-1 text-xs rounded-lg " + (mode === m ? "bg-panel2 text-ink" : "text-mute")}>
                  {m === "dark" ? "🌙" : "☀️"}
                </button>
              ))}
            </div>
            {hasSession
              ? <Link href="/dashboard" className="rounded-xl px-4 py-2 text-sm font-medium accent-bg">Open cockpit</Link>
              : <Link href="/login" className="rounded-xl px-4 py-2 text-sm font-medium accent-bg">Get started</Link>}
          </div>
        </header>

        {/* hero */}
        <section className="max-w-6xl mx-auto px-6 pt-16 pb-10 text-center">
          <h1 className="display display-tight text-5xl md:text-7xl lg:text-8xl mt-4 leading-[1.02] fade-up">
            The marketing brain<br /><span className="accent-text">that fetches.</span>
          </h1>
          <p className="text-lg md:text-xl text-ink2 max-w-2xl mx-auto mt-7 fade-up">
            Point Marketing Dog at your website. It learns your brand, skins itself in your colours, then
            plans, writes, critiques and publishes on-brand content and video across every channel — while you sleep.
          </p>
          <div className="flex items-center justify-center gap-3 mt-9 fade-up">
            <Link href="/login" className="rounded-xl px-5 py-3 font-medium accent-bg shadow-glow">Fetch my brand →</Link>
            <a href="#how" className="rounded-xl px-5 py-3 font-medium glass">See how it works</a>
          </div>
        </section>

        {/* live BrandSkin demo */}
        <section id="skin" className="max-w-4xl mx-auto px-6 mb-24">
          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
              <div className="text-left">
                <div className="text-[11px] uppercase tracking-widest accent-text font-mono">BrandSkin · live</div>
                <div className="text-ink2 text-sm mt-1">Tap a brand — this whole page re-skins, guaranteed readable.</div>
              </div>
              <span className="text-[11px] font-bold rounded-full px-2.5 py-1"
                style={{ background: audit.pass ? "var(--good)" : "var(--danger)", color: "var(--accent-ink)" }}>
                {audit.pass ? "WCAG AA ✓" : "review"}
              </span>
            </div>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Preset brands">
              {PRESET_BRANDS.map((p) => {
                const active = p.primary.toLowerCase() === brand.primary.toLowerCase();
                return (
                  <button key={p.name} title={p.name} aria-label={p.name} aria-pressed={active}
                    onClick={() => setBrand(p)}
                    className="size-9 rounded-lg border-2 focus-ring transition"
                    style={{
                      background: p.accent ? `linear-gradient(135deg, ${p.primary} 50%, ${p.accent} 50%)` : p.primary,
                      borderColor: active ? "var(--ink)" : "var(--line)",
                    }} />
                );
              })}
            </div>
          </div>
        </section>

        {/* how */}
        <section id="how" className="max-w-6xl mx-auto px-6 mb-24">
          <h2 className="display text-3xl md:text-4xl mb-2">Sniff → Decide → Make → Gate → Ship → Learn</h2>
          <p className="text-ink2 max-w-2xl">A closed loop that gets smarter every cycle.</p>
          <div className="grid sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-8">
            {[["01", "Sniff", "Scan site, products, trends; extract palette + voice"],
              ["02", "Decide", "Score demand × trend × audience into a calendar"],
              ["03", "Make", "Specialist agents draft in your voice"],
              ["04", "Gate", "Critic blocks off-brand before a human sees it"],
              ["05", "Ship", "One-click native publishing everywhere"],
              ["06", "Learn", "Winners feed the brain; next cycle scores higher"]].map(([n, h, d]) => (
              <div key={n} className="glass rounded-xl p-4">
                <div className="font-mono text-xs accent-text">{n}</div>
                <div className="font-semibold mt-1.5">{h}</div>
                <div className="text-mute text-xs mt-1">{d}</div>
              </div>
            ))}
          </div>
        </section>

        {/* features */}
        <section id="features" className="max-w-6xl mx-auto px-6 pb-28">
          <div className="grid md:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div key={f.t} className="glass rounded-xl p-6">
                <div className="size-10 rounded-xl grid place-items-center mb-3 text-xl"
                  style={{ background: "color-mix(in srgb, var(--accent) 16%, transparent)" }} aria-hidden="true">{f.i}</div>
                <h3 className="text-lg font-semibold">{f.t}</h3>
                <p className="text-mute text-sm mt-1.5">{f.d}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
