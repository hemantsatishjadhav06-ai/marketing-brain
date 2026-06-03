"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Brain = {
  id: string;
  brand_id: string;
  voice: string;
  tone: string;
  banned_phrases: string[];
  seo_keywords: string[];
  geo_prompts: string[];
  competitors: string[];
  cta_rules: any;
  platform_rules: any;
  visual_rules: any;
  content_templates: any;
};

type Refinements = {
  days: number;
  winners_analyzed: number;
  proposals: {
    add_seo_keywords: string[];
    voice_exemplars: string[];
    channel_mix_shift: Record<string, number>;
    banned_regressions: { content_item_id: string; banned: string[] }[];
  };
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);
  const { data, mutate } = useSWR<Brain>(brandId ? `/brands/${brandId}/brain` : null, apiFetcher);
  const { data: refinements, mutate: mutateRefine } = useSWR<Refinements>(
    brandId ? `/brands/${brandId}/brain/refinements?days=30` : null,
    apiFetcher,
  );

  const [voice, setVoice] = useState("");
  const [tone, setTone] = useState("");
  const [banned, setBanned] = useState("");
  const [seo, setSeo] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!data) return;
    setVoice(data.voice || "");
    setTone(data.tone || "");
    setBanned((data.banned_phrases || []).join("\n"));
    setSeo((data.seo_keywords || []).join("\n"));
    setCompetitors((data.competitors || []).join("\n"));
  }, [data]);

  async function acceptKeywords(keywords: string[]) {
    if (!brandId || keywords.length === 0) return;
    try {
      const r = await api<{ added: string[]; total: number }>(
        `/brands/${brandId}/brain/refinements/accept-seo`,
        { method: "POST", body: JSON.stringify({ keywords }) },
      );
      toast.success(`Added ${r.added.length} keywords (total ${r.total})`);
      mutate(); mutateRefine();
    } catch (e: any) { toast.error(e.message); }
  }

  async function save() {
    if (!brandId) return;
    setSaving(true);
    try {
      await api(`/brands/${brandId}/brain`, {
        method: "PUT",
        body: JSON.stringify({
          voice,
          tone,
          banned_phrases: banned.split("\n").map((s) => s.trim()).filter(Boolean),
          seo_keywords: seo.split("\n").map((s) => s.trim()).filter(Boolean),
          competitors: competitors.split("\n").map((s) => s.trim()).filter(Boolean),
        }),
      });
      toast.success("Brand brain saved");
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Brand Brain"
        description="What the agents reach for whenever they speak. Banned phrases hard-fail the critic; SEO keywords boost brand-fit scores."
        action={<Button onClick={save} disabled={!brandId || saving}>{saving ? "Saving…" : "Save"}</Button>}
      />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="p-4">
            <div className="text-xs font-mono text-mute mb-2">VOICE</div>
            <textarea value={voice} onChange={(e) => setVoice(e.target.value)} rows={5}
              className="w-full rounded-xl border border-line bg-panel2 px-3 py-2 text-sm" />
          </Card>
          <Card className="p-4">
            <div className="text-xs font-mono text-mute mb-2">TONE</div>
            <textarea value={tone} onChange={(e) => setTone(e.target.value)} rows={5}
              className="w-full rounded-xl border border-line bg-panel2 px-3 py-2 text-sm" />
          </Card>
          <Card className="p-4">
            <div className="text-xs font-mono text-mute mb-2">BANNED PHRASES (one per line)</div>
            <textarea value={banned} onChange={(e) => setBanned(e.target.value)} rows={8}
              className="w-full rounded-xl border border-line bg-panel2 px-3 py-2 text-sm font-mono" />
          </Card>
          <Card className="p-4">
            <div className="text-xs font-mono text-mute mb-2">SEO KEYWORDS (one per line)</div>
            <textarea value={seo} onChange={(e) => setSeo(e.target.value)} rows={8}
              className="w-full rounded-xl border border-line bg-panel2 px-3 py-2 text-sm font-mono" />
          </Card>
          <Card className="p-4 lg:col-span-2">
            <div className="text-xs font-mono text-mute mb-2">COMPETITORS / SUBREDDITS (one per line — drives trend ingest)</div>
            <textarea value={competitors} onChange={(e) => setCompetitors(e.target.value)} rows={5}
              className="w-full rounded-xl border border-line bg-panel2 px-3 py-2 text-sm font-mono" />
          </Card>

          <Card className="p-4 lg:col-span-2">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-mono text-mute">REFINEMENT PROPOSALS (from winning content, last 30d)</div>
              <button onClick={() => mutateRefine()} className="text-xs text-tennis font-mono hover:underline">re-analyse</button>
            </div>
            {!refinements || refinements.winners_analyzed === 0 ? (
              <div className="text-sm text-mute">No performance data yet. Record some metrics in Analytics first.</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <div className="text-[10px] font-mono text-mute uppercase mb-2">add seo keywords</div>
                  <div className="flex flex-wrap gap-1.5">
                    {refinements.proposals.add_seo_keywords.length === 0 && <span className="text-mute text-xs">No new keywords.</span>}
                    {refinements.proposals.add_seo_keywords.map((k) => (
                      <button key={k} onClick={() => acceptKeywords([k])}
                        className="text-xs font-mono px-2 py-1 rounded bg-panel2 hover:bg-tennis/15 hover:text-tennis">
                        + {k}
                      </button>
                    ))}
                  </div>
                  {refinements.proposals.add_seo_keywords.length > 0 && (
                    <button onClick={() => acceptKeywords(refinements.proposals.add_seo_keywords)}
                      className="mt-2 text-xs text-tennis hover:underline">Accept all →</button>
                  )}
                </div>
                <div>
                  <div className="text-[10px] font-mono text-mute uppercase mb-2">winning voice exemplars</div>
                  <ul className="space-y-1 text-xs text-mute">
                    {refinements.proposals.voice_exemplars.slice(0, 6).map((v, i) => <li key={i}>· {v}</li>)}
                    {refinements.proposals.voice_exemplars.length === 0 && <li>None.</li>}
                  </ul>
                </div>
                <div>
                  <div className="text-[10px] font-mono text-mute uppercase mb-2">channel mix in winners</div>
                  <ul className="space-y-1 text-xs">
                    {Object.entries(refinements.proposals.channel_mix_shift).map(([p, pct]) => (
                      <li key={p} className="flex justify-between"><span className="font-mono text-mute">{p}</span><span className="font-mono">{pct}%</span></li>
                    ))}
                  </ul>
                  {refinements.proposals.banned_regressions.length > 0 && (
                    <div className="mt-3 p-2 rounded bg-red-500/10 border border-red-500/30 text-xs text-red-300">
                      ⚠ {refinements.proposals.banned_regressions.length} winner(s) contained banned phrases.
                    </div>
                  )}
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
    </AppShell>
  );
}
