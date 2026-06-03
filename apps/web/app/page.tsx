"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getToken } from "@/lib/api";

const FEATURES = [
  { t: "Idea Mill", d: "An agent that reads your brand brain, products, and live trends — then drips you 40+ scored content ideas a day." },
  { t: "Calendar Agent", d: "Drag-drop month grid that auto-fills to your cadence rules. Every cell carries the AI reason it's there." },
  { t: "Specialist agents", d: "Static post · carousel · blog · email · short video. Each one knows your voice, your products, your platform rules." },
  { t: "Critic v2", d: "Cross-sport hard gate first, then a 10-criterion LLM rubric. Nothing reaches publish that doesn't pass." },
  { t: "Native publishing", d: "X · Instagram · LinkedIn · Pinterest · YouTube · TikTok · Klaviyo · any webhook. Or export a clean bundle." },
  { t: "Brand-brain learns", d: "Winning content's keywords + CTAs feed back into your brand brain. The next cycle scores higher." },
];

const SPORTS = [
  { name: "Tennis", color: "#CCFF00" },
  { name: "Padel", color: "#22D3EE" },
  { name: "Pickleball", color: "#F59E0B" },
  { name: "Badminton", color: "#A78BFA" },
  { name: "Squash", color: "#EF4444" },
];

export default function Landing() {
  const [hasSession, setHasSession] = useState(false);
  useEffect(() => { setHasSession(!!getToken()); }, []);

  return (
    <div className="relative bg-aurora min-h-screen overflow-hidden">
      <div className="noise absolute inset-0" />
      <div className="relative">
        {/* nav */}
        <header className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="grid grid-cols-2 gap-0.5">
              {SPORTS.slice(0, 4).map((s) => (
                <span key={s.name} className="size-2 rounded-sm" style={{ background: s.color }} />
              ))}
            </div>
            <span className="display text-lg">Marketing Brain</span>
          </Link>
          <nav className="hidden md:flex items-center gap-7 text-sm text-mute">
            <a href="#features" className="hover:text-ink">Features</a>
            <a href="#agents" className="hover:text-ink">Agents</a>
            <a href="#how" className="hover:text-ink">How it works</a>
            <a href="https://github.com/hemantsatishjadhav06-ai/marketing-brain" className="hover:text-ink">GitHub</a>
          </nav>
          <div className="flex items-center gap-2">
            {hasSession ? (
              <Link href="/dashboard" className="rounded-xl px-4 py-2 text-sm font-medium accent-bg hover:opacity-90">Open cockpit</Link>
            ) : (
              <>
                <Link href="/login" className="text-sm text-mute hover:text-ink px-3 py-2">Log in</Link>
                <Link href="/login" className="rounded-xl px-4 py-2 text-sm font-medium accent-bg hover:opacity-90">Get started</Link>
              </>
            )}
          </div>
        </header>

        {/* hero */}
        <section className="max-w-6xl mx-auto px-6 pt-16 pb-24 text-center">
          <div className="inline-flex items-center gap-2 text-xs font-mono text-mute glass rounded-full px-3 py-1.5 fade-up">
            <span className="size-1.5 rounded-full" style={{ background: "var(--accent)" }} />
            v0.4 · 8 publishers · 13 agents · brand-isolated
          </div>
          <h1 className="display display-tight text-5xl md:text-7xl lg:text-8xl mt-7 leading-[1.02] fade-up" style={{ animationDelay: "60ms" }}>
            An AI marketing team<br />
            <span className="accent-text">for every sport vertical.</span>
          </h1>
          <p className="text-lg md:text-xl text-ink2 max-w-2xl mx-auto mt-7 fade-up" style={{ animationDelay: "120ms" }}>
            Marketing Brain runs your content operation end-to-end: scored ideas, a planned calendar, on-brand drafts, brand-safe critique, and one-click publishing across every channel — without ever bleeding voice across brands.
          </p>
          <div className="flex items-center justify-center gap-3 mt-9 fade-up" style={{ animationDelay: "180ms" }}>
            <Link href="/login" className="rounded-xl px-5 py-3 font-medium accent-bg hover:opacity-90 shadow-glow">Open the cockpit →</Link>
            <a href="#how" className="rounded-xl px-5 py-3 font-medium glass hover:bg-panel2">See how it works</a>
          </div>

          {/* sport pills */}
          <div className="flex flex-wrap items-center justify-center gap-2 mt-10 fade-up" style={{ animationDelay: "240ms" }}>
            {SPORTS.map((s) => (
              <span key={s.name} className="rounded-full px-3 py-1 text-xs font-mono glass" style={{ color: s.color }}>
                ● {s.name}
              </span>
            ))}
          </div>
        </section>

        {/* mock dashboard preview */}
        <section className="max-w-6xl mx-auto px-6 -mt-4 mb-24">
          <div className="glass rounded-xl p-2 shadow-soft">
            <div className="flex items-center gap-1.5 px-3 py-2">
              <span className="size-2.5 rounded-full bg-danger" />
              <span className="size-2.5 rounded-full bg-warn" />
              <span className="size-2.5 rounded-full bg-good" />
              <span className="ml-3 text-xs font-mono text-mute">marketing-brain.app/dashboard</span>
            </div>
            <div className="rounded-lg overflow-hidden border hairline">
              <div className="grid grid-cols-[200px_1fr] bg-panel">
                <div className="border-r hairline p-3 space-y-1 text-xs text-mute">
                  {["Dashboard", "Brands", "Brand Brain", "Trends", "Ideas", "Studio", "Calendar", "Jobs", "Reviews", "Library", "Publishing", "Analytics", "Settings"].map((n, i) => (
                    <div key={n} className={"px-2 py-1.5 rounded " + (i === 0 ? "bg-panel2 text-ink" : "")}>{n}</div>
                  ))}
                </div>
                <div className="p-5">
                  <div className="grid grid-cols-4 gap-3">
                    {[
                      { l: "BRANDS", v: "5" },
                      { l: "CALENDAR ENTRIES", v: "120" },
                      { l: "MTD SPEND", v: "$47" },
                      { l: "REVIEW QUEUE", v: "8" },
                    ].map((k) => (
                      <div key={k.l} className="glass rounded p-3">
                        <div className="text-[10px] font-mono text-mute">{k.l}</div>
                        <div className="display text-3xl mt-1">{k.v}</div>
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <div className="glass rounded p-3">
                      <div className="text-[10px] font-mono text-mute mb-2">TOP-SCORED IDEAS</div>
                      {[["92.4", "How to choose grip size — beginner guide", "instagram"],
                        ["88.1", "5 mistakes beginners make with string tension", "youtube"],
                        ["86.7", "Why most racket weight advice is wrong", "blog"]].map(([s, t, p]) => (
                          <div key={t} className="flex items-center gap-3 text-xs py-1">
                            <span className="font-mono accent-text w-10 text-right">{s}</span>
                            <span className="font-mono text-mute w-16">{p}</span>
                            <span className="truncate">{t}</span>
                          </div>
                        ))}
                    </div>
                    <div className="glass rounded p-3">
                      <div className="text-[10px] font-mono text-mute mb-2">RECENT JOBS</div>
                      {[["idea_mill.run", "done"], ["calendar.generate", "done"], ["static_post.draft", "running"], ["critic.score", "running"]].map(([t, s]) => (
                        <div key={t as string} className="flex items-center justify-between text-xs py-1">
                          <span className="font-mono text-mute">{t}</span>
                          <span className={`font-mono ${s === "done" ? "text-good" : "accent-text"}`}>● {s}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* features */}
        <section id="features" className="max-w-6xl mx-auto px-6 py-20">
          <div className="text-center">
            <div className="text-xs font-mono text-mute uppercase tracking-widest">Why it exists</div>
            <h2 className="display text-4xl md:text-5xl mt-3">The whole content operation, in one loop.</h2>
            <p className="text-ink2 max-w-2xl mx-auto mt-4">Replaces a 5-person content team with one cockpit you can open every morning.</p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mt-12">
            {FEATURES.map((f) => (
              <div key={f.t} className="glass rounded-lg p-6 hover:translate-y-[-2px] transition">
                <div className="size-9 rounded-lg flex items-center justify-center accent-bg mb-4 font-mono">●</div>
                <div className="display text-2xl">{f.t}</div>
                <p className="text-ink2 text-sm mt-2 leading-relaxed">{f.d}</p>
              </div>
            ))}
          </div>
        </section>

        {/* agents grid */}
        <section id="agents" className="max-w-6xl mx-auto px-6 py-20">
          <div className="grid lg:grid-cols-[1fr_2fr] gap-8 items-start">
            <div>
              <div className="text-xs font-mono text-mute uppercase tracking-widest">Agents</div>
              <h2 className="display text-4xl md:text-5xl mt-3">13 specialist agents.<br/>One brain.</h2>
              <p className="text-ink2 mt-4">Each agent gets the brand voice + the hard cross-sport rule baked into its system prompt. Nothing slips.</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {[
                "Orchestrator", "Idea Mill", "Calendar",
                "Static Post", "Carousel", "Blog",
                "Email", "Short Video", "Reel + Voice",
                "Long Video", "Critic v2", "Repurpose",
                "Publish Export",
              ].map((a) => (
                <div key={a} className="glass rounded p-3 text-sm">
                  <div className="text-[10px] font-mono text-mute">agent</div>
                  <div className="mt-1">{a}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* how it works */}
        <section id="how" className="max-w-6xl mx-auto px-6 py-20">
          <div className="text-center">
            <div className="text-xs font-mono text-mute uppercase tracking-widest">How it works</div>
            <h2 className="display text-4xl md:text-5xl mt-3">From brand brain to published post.</h2>
          </div>
          <ol className="grid md:grid-cols-2 lg:grid-cols-4 gap-3 mt-12">
            {[
              ["01", "Brand brain", "Voice, banned phrases, SEO keywords, competitors. The agents read this before they speak."],
              ["02", "Ideas + Calendar", "Idea Mill scores 40+ ideas. Calendar Agent lays them across 30 days honouring cadence."],
              ["03", "Draft + Critique", "Specialist agents draft, Critic v2 scores with cross-sport hard gate first."],
              ["04", "Publish + Learn", "Native publish to 8 channels. Winning content feeds back into the brain."],
            ].map(([n, t, d]) => (
              <li key={n} className="glass rounded-lg p-6">
                <div className="font-mono text-xs accent-text">{n}</div>
                <div className="display text-xl mt-2">{t}</div>
                <div className="text-ink2 text-sm mt-2">{d}</div>
              </li>
            ))}
          </ol>
        </section>

        {/* cta */}
        <section className="max-w-4xl mx-auto px-6 py-24 text-center">
          <div className="glass rounded-xl p-12 shadow-soft relative overflow-hidden">
            <div className="absolute inset-0 -z-10" style={{ background: "radial-gradient(420px 220px at 50% 0%, color-mix(in srgb, var(--accent) 22%, transparent), transparent 70%)" }} />
            <h2 className="display text-4xl md:text-5xl">Run the demo cockpit.</h2>
            <p className="text-ink2 mt-3 max-w-lg mx-auto">A seeded tennis brand is waiting for you. Generate ideas, regenerate a calendar, draft your first post in under three minutes.</p>
            <div className="flex items-center justify-center gap-3 mt-7">
              <Link href="/login" className="rounded-xl px-5 py-3 font-medium accent-bg hover:opacity-90 shadow-glow">Open cockpit →</Link>
              <a href="https://github.com/hemantsatishjadhav06-ai/marketing-brain" className="rounded-xl px-5 py-3 font-medium glass hover:bg-panel2">View on GitHub</a>
            </div>
            <div className="text-xs font-mono text-mute mt-6">owner@marketing-brain.local · changeme</div>
          </div>
        </section>

        <footer className="max-w-6xl mx-auto px-6 py-8 border-t hairline flex flex-col md:flex-row items-center justify-between text-xs text-mute gap-2">
          <div>© Marketing Brain · v0.4 · phase 4</div>
          <div className="font-mono">brand-isolated · cost-guarded · cross-sport-safe</div>
        </footer>
      </div>
    </div>
  );
}
