"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Trend = {
  id: string;
  source: string;
  topic: string;
  keyword: string;
  signal_strength: number;
  slope: number;
  captured_at: string;
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [topic, setTopic] = useState("");
  const [keyword, setKeyword] = useState("");
  const [signal, setSignal] = useState(60);
  const [slope, setSlope] = useState(0.3);
  const [source, setSource] = useState("manual");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const { data, mutate } = useSWR<Trend[]>(brandId ? `/brands/${brandId}/trends?limit=100` : null, apiFetcher);

  async function add() {
    if (!brandId || !topic) return;
    setBusy(true);
    try {
      await api(`/brands/${brandId}/trends`, {
        method: "POST",
        body: JSON.stringify({ source, topic, keyword, signal_strength: signal, slope, payload: {} }),
      });
      setTopic(""); setKeyword("");
      toast.success("Trend added");
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <PageHeader title="Trends" description="Signals the scoring engine reads. Higher signal_strength + recent capture = more lift." />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && (
        <Card className="p-4 mb-4">
          <div className="text-xs font-mono text-mute mb-3">ADD A TREND</div>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
            <select value={source} onChange={(e) => setSource(e.target.value)} className="rounded-xl bg-panel2 border border-line px-3 py-2 text-sm">
              {["manual", "google_trends", "serp", "youtube", "competitor", "reddit"].map((s) => <option key={s}>{s}</option>)}
            </select>
            <Input placeholder="topic" value={topic} onChange={(e) => setTopic(e.target.value)} />
            <Input placeholder="keyword (optional)" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
            <Input type="number" placeholder="signal 0-100" value={signal} onChange={(e) => setSignal(Number(e.target.value))} />
            <Input type="number" step="0.1" placeholder="slope -1..1" value={slope} onChange={(e) => setSlope(Number(e.target.value))} />
            <Button onClick={add} disabled={busy}>Add</Button>
          </div>
        </Card>
      )}
      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-panel2 text-mute font-mono text-xs">
            <tr>
              <th className="text-left p-3">Topic</th>
              <th className="text-left p-3 w-32">Keyword</th>
              <th className="text-left p-3 w-32">Source</th>
              <th className="text-left p-3 w-24">Signal</th>
              <th className="text-left p-3 w-24">Slope</th>
              <th className="text-left p-3 w-44">Captured</th>
            </tr>
          </thead>
          <tbody>
            {(data || []).map((t) => (
              <tr key={t.id} className="border-t border-line">
                <td className="p-3">{t.topic}</td>
                <td className="p-3 font-mono text-xs">{t.keyword}</td>
                <td className="p-3 font-mono text-xs">{t.source}</td>
                <td className="p-3 font-mono text-tennis">{t.signal_strength.toFixed(0)}</td>
                <td className="p-3 font-mono">{t.slope.toFixed(2)}</td>
                <td className="p-3 text-xs text-mute">{new Date(t.captured_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </AppShell>
  );
}
