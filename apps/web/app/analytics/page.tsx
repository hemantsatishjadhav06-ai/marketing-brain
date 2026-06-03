"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader } from "@/components/ui";
import { api, apiFetcher, getToken } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Summary = {
  totals: { impressions: number; engagements: number; clicks: number; conversions: number; revenue: number; items: number };
  by_platform: Record<string, { impressions: number; engagements: number; revenue: number; items: number }>;
  top_content: Array<{
    content_item_id: string; platform: string; content_type: string;
    angle: string; impressions: number; engagements: number; revenue: number; engagement_rate: number;
  }>;
  days: number;
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [contentId, setContentId] = useState("");
  const [imp, setImp] = useState(0);
  const [eng, setEng] = useState(0);
  const [clicks, setClicks] = useState(0);
  const [conv, setConv] = useState(0);
  const [rev, setRev] = useState(0);

  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const { data, mutate } = useSWR<Summary>(brandId ? `/brands/${brandId}/analytics/summary?days=${days}` : null, apiFetcher);

  async function addPerf() {
    if (!brandId || !contentId) return;
    try {
      await api(`/brands/${brandId}/analytics/perf`, {
        method: "POST",
        body: JSON.stringify({
          content_item_id: contentId,
          impressions: imp,
          engagements: eng,
          clicks,
          conversions: conv,
          revenue: rev,
          period: "rolling_7d",
        }),
      });
      toast.success("Performance recorded");
      setContentId(""); setImp(0); setEng(0); setClicks(0); setConv(0); setRev(0);
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function uploadCsv(file: File) {
    if (!brandId) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const t = getToken();
      const r = await fetch(`/api/brands/${brandId}/analytics/perf/csv`, {
        method: "POST",
        body: fd,
        headers: t ? { Authorization: `Bearer ${t}` } : {},
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || JSON.stringify(j));
      toast.success(`Ingested ${j.rows_ingested} rows`);
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Analytics"
        description="Performance per content item. Phase 2 = manual + CSV ingest. Phase 3 = native platform pulls."
        action={
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-lg bg-panel2 border border-line px-3 py-2 text-sm">
            <option value={7}>7d</option><option value={30}>30d</option><option value={90}>90d</option>
          </select>
        }
      />

      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            {[
              { k: "items", label: "ITEMS WITH DATA" },
              { k: "impressions", label: "IMPRESSIONS" },
              { k: "engagements", label: "ENGAGEMENTS" },
              { k: "clicks", label: "CLICKS" },
              { k: "revenue", label: "REVENUE $" },
            ].map((c) => (
              <Card key={c.k} className="p-4">
                <div className="text-xs font-mono text-mute">{c.label}</div>
                <div className="font-serif text-2xl mt-1">{((data?.totals as any)?.[c.k] ?? 0).toLocaleString()}</div>
              </Card>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <Card className="p-5">
              <div className="text-xs font-mono text-mute mb-3">BY PLATFORM</div>
              <div className="space-y-1.5">
                {Object.entries(data?.by_platform || {}).sort((a, b) => b[1].engagements - a[1].engagements).map(([p, v]) => (
                  <div key={p} className="flex items-center justify-between text-sm">
                    <span className="font-mono">{p}</span>
                    <span className="text-mute">{v.engagements.toLocaleString()} eng · {v.items} items · ${v.revenue.toFixed(0)}</span>
                  </div>
                ))}
                {!Object.keys(data?.by_platform || {}).length && <div className="text-mute text-sm">No data yet.</div>}
              </div>
            </Card>
            <Card className="p-5">
              <div className="text-xs font-mono text-mute mb-3">RECORD A METRIC</div>
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="content_item_id" value={contentId} onChange={(e) => setContentId(e.target.value)} className="col-span-2" />
                <Input type="number" placeholder="impressions" value={imp || ""} onChange={(e) => setImp(+e.target.value)} />
                <Input type="number" placeholder="engagements" value={eng || ""} onChange={(e) => setEng(+e.target.value)} />
                <Input type="number" placeholder="clicks" value={clicks || ""} onChange={(e) => setClicks(+e.target.value)} />
                <Input type="number" placeholder="conversions" value={conv || ""} onChange={(e) => setConv(+e.target.value)} />
                <Input type="number" placeholder="revenue $" value={rev || ""} onChange={(e) => setRev(+e.target.value)} className="col-span-2" />
                <Button onClick={addPerf}>Record</Button>
                <label className="inline-flex items-center justify-center rounded-xl border border-line px-3 py-2 text-sm cursor-pointer hover:bg-panel2">
                  <input type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && uploadCsv(e.target.files[0])} />
                  Upload CSV
                </label>
              </div>
            </Card>
          </div>

          <Card className="overflow-hidden">
            <div className="text-xs font-mono text-mute p-3">TOP CONTENT</div>
            <table className="w-full text-sm">
              <thead className="bg-panel2 text-mute font-mono text-xs">
                <tr>
                  <th className="text-left p-3">Angle</th>
                  <th className="text-left p-3 w-24">Platform</th>
                  <th className="text-right p-3 w-24">Impressions</th>
                  <th className="text-right p-3 w-24">Engagements</th>
                  <th className="text-right p-3 w-24">ER %</th>
                  <th className="text-right p-3 w-24">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {(data?.top_content || []).map((t) => (
                  <tr key={t.content_item_id} className="border-t border-line">
                    <td className="p-3"><Link href={`/studio/${t.content_item_id}`} className="hover:text-tennis line-clamp-1">{t.angle}</Link></td>
                    <td className="p-3 font-mono text-xs">{t.platform}</td>
                    <td className="p-3 text-right font-mono">{t.impressions.toLocaleString()}</td>
                    <td className="p-3 text-right font-mono">{t.engagements.toLocaleString()}</td>
                    <td className="p-3 text-right font-mono text-tennis">{t.engagement_rate.toFixed(1)}</td>
                    <td className="p-3 text-right font-mono">${t.revenue.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </AppShell>
  );
}
