"use client";
// BrandThemeStudio — the Settings → Appearance panel.
// Lets an operator dial in their brand colours and watch the whole cockpit
// re-skin live, with a real-time WCAG audit. Wire `onSave` to PUT /orgs/me/theme
// (or Supabase brands.theme).

import { useState } from "react";
import { auditTheme, buildTheme, PRESET_BRANDS, type BrandInput } from "@/lib/theme/brandskin";
import { useBrandTheme } from "@/lib/theme/ThemeProvider";

const HEX = /^#?[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$/;
const norm = (s: string) => (s.startsWith("#") ? s : "#" + s);

export function BrandThemeStudio({ onSave }: { onSave?: (b: BrandInput) => Promise<void> | void }) {
  const { brand, setBrand, mode, setMode, theme } = useBrandTheme();
  const [saving, setSaving] = useState(false);
  const audit = auditTheme(theme[mode]);

  const update = (patch: Partial<BrandInput>) => setBrand({ ...brand, ...patch });

  return (
    <section aria-labelledby="appearance-h" className="rounded-xl glass p-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 id="appearance-h" className="display text-2xl">Appearance</h2>
          <p className="text-mute text-sm mt-1 max-w-md">
            Your brand colours skin the entire product. We auto-correct them to stay
            WCAG-AA legible — paste anything.
          </p>
        </div>
        <div className="inline-flex rounded-xl border hairline bg-panel p-1" role="group" aria-label="Colour mode">
          {(["dark", "light"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              aria-pressed={mode === m}
              className={"px-3 py-1.5 text-sm rounded-lg transition " +
                (mode === m ? "bg-panel2 text-ink" : "text-mute hover:text-ink")}
            >
              {m === "dark" ? "🌙 Dark" : "☀️ Light"}
            </button>
          ))}
        </div>
      </div>

      {/* presets */}
      <div className="mt-5">
        <div className="text-[11px] uppercase tracking-widest text-mute font-mono mb-2">Quick brands</div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Preset brands">
          {PRESET_BRANDS.map((p) => {
            const active = p.primary.toLowerCase() === brand.primary.toLowerCase();
            return (
              <button
                key={p.name}
                title={p.name}
                aria-label={p.name}
                aria-pressed={active}
                onClick={() => setBrand(p)}
                className="size-8 rounded-lg border-2 transition focus-ring"
                style={{
                  background: p.accent
                    ? `linear-gradient(135deg, ${p.primary} 50%, ${p.accent} 50%)`
                    : p.primary,
                  borderColor: active ? "var(--ink)" : "var(--line)",
                  boxShadow: active ? "0 0 0 2px var(--bg), 0 0 0 4px var(--ink)" : undefined,
                }}
              />
            );
          })}
        </div>
      </div>

      {/* colour inputs */}
      <div className="grid sm:grid-cols-2 gap-4 mt-5">
        {(["primary", "accent"] as const).map((key) => {
          const val = (key === "primary" ? brand.primary : brand.accent || brand.primary);
          return (
            <label key={key} className="block">
              <span className="text-[11px] uppercase tracking-widest text-mute font-mono">{key}</span>
              <span className="mt-1.5 flex items-center gap-2 rounded-xl border hairline bg-panel2 px-3 py-2">
                <input
                  type="color"
                  aria-label={`${key} colour`}
                  value={HEX.test(val) ? norm(val) : "#000000"}
                  onChange={(e) => update({ [key]: e.target.value } as Partial<BrandInput>)}
                  className="size-7 cursor-pointer bg-transparent"
                />
                <input
                  type="text"
                  spellCheck={false}
                  value={val}
                  aria-label={`${key} hex`}
                  onChange={(e) => { if (HEX.test(e.target.value)) update({ [key]: norm(e.target.value) } as Partial<BrandInput>); }}
                  className="w-full bg-transparent font-mono text-sm text-ink outline-none focus-ring rounded"
                />
              </span>
            </label>
          );
        })}
      </div>

      {/* live audit */}
      <div className="mt-6 border-t hairline pt-4" aria-live="polite">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[11px] uppercase tracking-widest text-mute font-mono">Accessibility audit</span>
          <span
            className="text-[11px] font-bold rounded-full px-2 py-0.5"
            style={{ background: audit.pass ? "var(--good)" : "var(--danger)", color: "var(--accent-ink)" }}
          >
            {audit.pass ? "WCAG AA ✓" : "review"}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {audit.rows.map((r) => (
            <span key={r.name} className="inline-flex items-center gap-1.5 rounded-full border hairline px-2.5 py-1 text-[11px] font-mono">
              <span style={{ color: r.pass ? "var(--good)" : "var(--danger)" }}>{r.pass ? "✓" : "✕"}</span>
              {r.name} <b>{r.ratio}</b><span className="text-mute">/{r.min}</span>
            </span>
          ))}
        </div>
      </div>

      {onSave && (
        <div className="mt-6">
          <button
            disabled={saving || !audit.pass}
            onClick={async () => { setSaving(true); try { await onSave(brand); } finally { setSaving(false); } }}
            className="accent-bg rounded-xl px-4 py-2 text-sm font-medium shadow-glow disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save brand theme"}
          </button>
          {!audit.pass && <span className="text-danger text-xs ml-3">Resolve contrast issues before saving.</span>}
        </div>
      )}
    </section>
  );
}
