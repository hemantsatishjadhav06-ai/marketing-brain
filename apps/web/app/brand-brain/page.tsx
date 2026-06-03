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

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);
  const { data, mutate } = useSWR<Brain>(brandId ? `/brands/${brandId}/brain` : null, apiFetcher);

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
            <div className="text-xs font-mono text-mute mb-2">COMPETITORS (one per line)</div>
            <textarea value={competitors} onChange={(e) => setCompetitors(e.target.value)} rows={5}
              className="w-full rounded-xl border border-line bg-panel2 px-3 py-2 text-sm font-mono" />
          </Card>
        </div>
      )}
    </AppShell>
  );
}
