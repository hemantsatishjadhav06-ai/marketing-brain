"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, PageHeader, StatusPill } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Row = {
  id: string;
  platform: string;
  content_type: string;
  status: string;
  angle: string;
  agent_name: string;
  created_at: string;
};

type Target = {
  id: string;
  platform: string;
  mode: string;
  active: boolean;
  credentials: { configured: boolean; keys: string[] };
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const { data, mutate } = useSWR<Row[]>(brandId ? `/content?brand_id=${brandId}&status_filter=approved` : null, apiFetcher);
  const { data: targets } = useSWR<Target[]>(brandId ? `/brands/${brandId}/publish-targets` : null, apiFetcher);
  const platformToTarget = new Map((targets || []).map((t) => [t.platform, t]));

  async function exportItem(id: string) {
    setBusy(id);
    try {
      const r = await api<{ url: string; filename: string; bytes: number }>(`/publishing/export/${id}`, { method: "POST" });
      toast.success(`Bundle exported · ${(r.bytes / 1024).toFixed(0)} KB`);
      window.open(r.url, "_blank");
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function publishNow(id: string) {
    setBusy(id);
    try {
      const r = await api<{ ok: boolean; status: string; url?: string; error?: string }>(`/publishing/publish/${id}`, { method: "POST" });
      if (r.ok) {
        toast.success(`Published (${r.status})${r.url ? " · opening" : ""}`);
        if (r.url) window.open(r.url, "_blank");
      } else {
        toast.error(r.error || "Publish failed");
      }
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(null);
    }
  }

  const [selected, setSelected] = useState<Set<string>>(new Set());
  function toggle(id: string) {
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }
  async function bulkPublish() {
    if (selected.size === 0) return;
    setBusy("bulk");
    let ok = 0, fail = 0;
    for (const id of selected) {
      try {
        const r = await api<{ ok: boolean }>(`/publishing/publish/${id}`, { method: "POST" });
        if (r.ok) ok++; else fail++;
      } catch { fail++; }
    }
    setSelected(new Set());
    setBusy(null);
    toast.success(`Published ${ok}${fail ? ` · ${fail} failed` : ""}`);
    mutate();
  }
  async function bulkDownload() {
    if (selected.size === 0) return;
    setBusy("bulk-dl");
    try {
      const t = (await import("@/lib/api")).getToken();
      const r = await fetch("/api/publishing/export/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) },
        body: JSON.stringify({ content_ids: [...selected] }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `marketing-brain-bulk-${selected.size}.zip`; a.click();
      URL.revokeObjectURL(url);
      toast.success(`Downloaded ${selected.size} bundles`);
    } catch (e: any) { toast.error(e.message); }
    finally { setBusy(null); }
  }

  return (
    <AppShell>
      <PageHeader
        title="Publishing"
        description="Approved content. Configure a publish target per platform in Settings → Publish Targets; without one, we fall back to the export bundle."
        action={selected.size > 0 ? (
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-mute">{selected.size} selected</span>
            <Button variant="outline" onClick={() => setSelected(new Set())}>Clear</Button>
            <Button variant="outline" onClick={bulkDownload} disabled={busy === "bulk-dl"}>{busy === "bulk-dl" ? "…" : `Download ${selected.size}.zip`}</Button>
            <Button onClick={bulkPublish} disabled={busy === "bulk"}>{busy === "bulk" ? "…" : `Publish ${selected.size}`}</Button>
          </div>
        ) : undefined}
      />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && targets && targets.length > 0 && (
        <Card className="p-4 mb-4">
          <div className="text-xs font-mono text-mute mb-2">CONNECTED TARGETS</div>
          <div className="flex flex-wrap gap-2">
            {targets.map((t) => (
              <span key={t.id} className={`text-xs font-mono px-2 py-1 rounded ${t.active && t.mode === "api" && t.credentials.configured ? "bg-tennis/15 text-tennis" : "bg-panel2 text-mute"}`}>
                {t.platform} · {t.mode}{t.credentials.configured ? " · ✓ creds" : " · no creds"}
              </span>
            ))}
          </div>
        </Card>
      )}
      {brandId && data && data.length === 0 && (
        <Card className="p-10 text-center">
          <div className="font-serif text-2xl">No approved items yet</div>
          <div className="text-mute text-sm mt-2">Approve drafts from the Reviews page to populate this queue.</div>
        </Card>
      )}
      <div className="space-y-3">
        {(data || []).map((c) => {
          const t = platformToTarget.get(c.platform);
          const willPublish = t && t.mode === "api" && t.credentials.configured && t.active;
          return (
            <Card key={c.id} className="p-4 flex items-center gap-4">
              <input
                type="checkbox"
                checked={selected.has(c.id)}
                onChange={() => toggle(c.id)}
                className="size-4 accent-tennis"
                title="Select for bulk publish / download"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <StatusPill status={c.status} />
                  <span className="text-xs font-mono text-mute">{c.platform} · {c.content_type}</span>
                  {willPublish ? (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-tennis/15 text-tennis">API</span>
                  ) : (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-panel2 text-mute">EXPORT</span>
                  )}
                </div>
                <Link href={`/studio/${c.id}`} className="font-serif text-lg block mt-1 hover:text-tennis">{c.angle}</Link>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => exportItem(c.id)} disabled={busy === c.id}>
                  {busy === c.id ? "…" : "Export"}
                </Button>
                <Button onClick={() => publishNow(c.id)} disabled={busy === c.id}>
                  {busy === c.id ? "…" : (willPublish ? "Publish now" : "Publish (export)")}
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </AppShell>
  );
}
