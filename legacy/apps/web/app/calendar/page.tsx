"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Button, Card, PageHeader, StatusPill } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Entry = {
  id: string;
  date: string;             // YYYY-MM-DD
  platform: string;
  content_type: string;
  product_ids: string[];
  angle: string;
  score: number;
  reason: string;
  status: string;
  agent_name: string;
  content_item_id: string | null;
  position: number;
};

const PLATFORM_TONE: Record<string, string> = {
  instagram: "bg-pink-500/15 text-pink-300",
  youtube: "bg-red-500/15 text-red-300",
  blog: "bg-amber-500/15 text-amber-300",
  email: "bg-sky-500/15 text-sky-300",
  x: "bg-zinc-500/15 text-zinc-300",
  linkedin: "bg-blue-500/15 text-blue-300",
  tiktok: "bg-fuchsia-500/15 text-fuchsia-300",
  pinterest: "bg-rose-500/15 text-rose-300",
  reddit: "bg-orange-500/15 text-orange-300",
};

function addDays(d: Date, n: number): Date {
  const nd = new Date(d);
  nd.setDate(nd.getDate() + n);
  return nd;
}
function fmtKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [drafting, setDrafting] = useState<string | null>(null);

  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const key = brandId ? `/brands/${brandId}/calendar` : null;
  const { data, mutate } = useSWR<Entry[]>(key, apiFetcher);

  // build 30-day grid starting today
  const grid = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const days: { key: string; label: string; entries: Entry[] }[] = [];
    const byKey = new Map<string, Entry[]>();
    for (const e of data || []) {
      if (!byKey.has(e.date)) byKey.set(e.date, []);
      byKey.get(e.date)!.push(e);
    }
    for (let i = 0; i < 30; i++) {
      const d = addDays(today, i);
      const k = fmtKey(d);
      const label = `${d.toLocaleDateString("en", { weekday: "short" })} ${d.getDate()}/${d.getMonth() + 1}`;
      days.push({ key: k, label, entries: (byKey.get(k) || []).sort((a, b) => a.position - b.position) });
    }
    return days;
  }, [data]);

  async function regenerate() {
    if (!brandId) { toast.error("Select a brand first."); return; }
    setRunning(true);
    try {
      const r = await api<{ entries_created: number }>(
        `/brands/${brandId}/calendar/generate`,
        { method: "POST", body: JSON.stringify({ days: 30, replace_existing: true }) }
      );
      toast.success(`Calendar regenerated · ${r.entries_created} entries`);
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setRunning(false);
    }
  }

  async function moveEntry(entryId: string, dateKey: string) {
    if (!brandId) return;
    try {
      await api(`/brands/${brandId}/calendar/${entryId}/move`, {
        method: "PATCH",
        body: JSON.stringify({ date: dateKey, position: 0 }),
      });
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  async function draft(entryId: string) {
    if (!brandId) return;
    setDrafting(entryId);
    try {
      const r = await api<{ content_item_id: string }>(
        `/content/draft`,
        { method: "POST", body: JSON.stringify({ brand_id: brandId, entry_id: entryId }) }
      );
      toast.success("Draft created — open Studio to review");
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setDrafting(null);
    }
  }

  async function remove(entryId: string) {
    if (!brandId) return;
    try {
      await api(`/brands/${brandId}/calendar/${entryId}`, { method: "DELETE" });
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Calendar"
        description="30-day content plan from the Calendar agent. Drag entries between days. Click ‘Draft’ to fire the specialist agent."
        action={
          <Button onClick={regenerate} disabled={!brandId || running}>
            {running ? "Generating…" : "Regenerate 30-day plan"}
          </Button>
        }
      />

      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && (
        <div className="grid grid-cols-2 md:grid-cols-5 lg:grid-cols-6 gap-3">
          {grid.map((d) => (
            <div
              key={d.key}
              onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("ring-1", "ring-tennis"); }}
              onDragLeave={(e) => e.currentTarget.classList.remove("ring-1", "ring-tennis")}
              onDrop={(e) => {
                e.preventDefault();
                e.currentTarget.classList.remove("ring-1", "ring-tennis");
                const eid = e.dataTransfer.getData("text/plain");
                if (eid) moveEntry(eid, d.key);
              }}
              className="rounded-xl border border-line bg-panel p-2 min-h-[180px]"
            >
              <div className="text-xs font-mono text-mute mb-2">{d.label}</div>
              <div className="space-y-1.5">
                {d.entries.map((e) => (
                  <div
                    key={e.id}
                    draggable
                    onDragStart={(ev) => ev.dataTransfer.setData("text/plain", e.id)}
                    className="rounded-lg bg-panel2 border border-line p-2 cursor-grab active:cursor-grabbing"
                    title={e.reason}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${PLATFORM_TONE[e.platform] || "bg-panel2 text-mute"}`}>{e.platform}</span>
                      <span className="text-[10px] text-tennis font-mono">{e.score.toFixed(0)}</span>
                    </div>
                    <div className="text-xs mt-1.5 line-clamp-2">{e.angle}</div>
                    <div className="flex items-center justify-between mt-1.5">
                      <StatusPill status={e.status} />
                      <div className="flex gap-1">
                        {e.content_item_id ? (
                          <Link href={`/studio/${e.content_item_id}`} className="text-[10px] font-mono text-tennis hover:underline">Open</Link>
                        ) : (
                          <button
                            onClick={() => draft(e.id)}
                            disabled={drafting === e.id}
                            className="text-[10px] font-mono text-tennis hover:underline disabled:opacity-50"
                          >
                            {drafting === e.id ? "…" : "Draft"}
                          </button>
                        )}
                        <button
                          onClick={() => remove(e.id)}
                          className="text-[10px] font-mono text-mute hover:text-red-400"
                          title="Delete"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
