"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, PageHeader, StatusPill } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Idea = {
  id: string;
  title: string;
  angle: string;
  platform: string;
  content_type: string;
  product_ids: string[];
  score: number;
  reason: string;
  source: string;
  status: string;
  created_at: string;
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [sort, setSort] = useState<"score_desc" | "score_asc" | "created_desc">("score_desc");
  const [platform, setPlatform] = useState("");

  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const key = brandId
    ? `/brands/${brandId}/ideas?sort=${sort}${platform ? `&platform=${platform}` : ""}`
    : null;
  const { data, mutate, isLoading } = useSWR<Idea[]>(key, apiFetcher);

  async function generate() {
    if (!brandId) { toast.error("Select a brand first."); return; }
    setGenerating(true);
    try {
      const r = await api<{ ideas_persisted: number }>(
        `/brands/${brandId}/ideas/generate?count=40`,
        { method: "POST" }
      );
      toast.success(`Generated ${r.ideas_persisted} ideas`);
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setGenerating(false);
    }
  }

  async function rescore() {
    if (!brandId) return;
    try {
      const r = await api<{ rescored: number; avg_score: number }>(
        `/brands/${brandId}/score/run`,
        { method: "POST" }
      );
      toast.success(`Re-scored ${r.rescored} ideas (avg ${r.avg_score})`);
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Ideas"
        description="Scored content ideas. The Idea Mill agent generates them from brand brain + products + trends."
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={rescore} disabled={!brandId}>Re-score</Button>
            <Button onClick={generate} disabled={!brandId || generating}>
              {generating ? "Generating…" : "Generate 40 ideas"}
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <select
          className="rounded-lg bg-panel2 border border-line px-3 py-1.5 text-sm"
          value={sort}
          onChange={(e) => setSort(e.target.value as any)}
        >
          <option value="score_desc">Score ↓</option>
          <option value="score_asc">Score ↑</option>
          <option value="created_desc">Newest</option>
        </select>
        <select
          className="rounded-lg bg-panel2 border border-line px-3 py-1.5 text-sm"
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
        >
          <option value="">All platforms</option>
          {["instagram", "youtube", "blog", "email", "x", "linkedin", "tiktok", "pinterest", "reddit"].map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <span className="text-xs font-mono text-mute ml-auto">{data?.length ?? 0} ideas</span>
      </div>

      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && isLoading && <Card className="p-8 text-mute">Loading…</Card>}
      {brandId && data && data.length === 0 && (
        <Card className="p-10 text-center">
          <div className="font-serif text-2xl">No ideas yet</div>
          <div className="text-mute text-sm mt-2">Click "Generate 40 ideas" to fire the Idea Mill agent.</div>
        </Card>
      )}
      {data && data.length > 0 && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-panel2 text-mute font-mono text-xs">
              <tr>
                <th className="text-left p-3 w-16">Score</th>
                <th className="text-left p-3">Title / angle</th>
                <th className="text-left p-3 w-32">Platform</th>
                <th className="text-left p-3 w-32">Type</th>
                <th className="text-left p-3 w-28">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((i) => (
                <tr key={i.id} className="border-t border-line align-top hover:bg-panel2/50">
                  <td className="p-3 font-mono text-tennis">{i.score.toFixed(1)}</td>
                  <td className="p-3">
                    <div className="font-medium">{i.title}</div>
                    <div className="text-mute text-xs mt-0.5">{i.angle}</div>
                    {i.reason && (
                      <div className="text-mute text-xs mt-1 italic line-clamp-2">{i.reason}</div>
                    )}
                  </td>
                  <td className="p-3 font-mono text-xs">{i.platform}</td>
                  <td className="p-3 font-mono text-xs">{i.content_type}</td>
                  <td className="p-3"><StatusPill status={i.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AppShell>
  );
}
