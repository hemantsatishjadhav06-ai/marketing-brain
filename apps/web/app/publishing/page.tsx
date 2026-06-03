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

  async function publish(id: string) {
    try {
      await api(`/content/${id}/transition?to=scheduled`, { method: "POST" });
      await api(`/content/${id}/transition?to=published`, { method: "POST" });
      toast.success("Marked published");
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    }
  }

  return (
    <AppShell>
      <PageHeader title="Publishing" description="Approved content. Export a manual-post bundle today; API integrations land in Phase 3." />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && data && data.length === 0 && (
        <Card className="p-10 text-center">
          <div className="font-serif text-2xl">No approved items yet</div>
          <div className="text-mute text-sm mt-2">Approve drafts from the Reviews page to populate this queue.</div>
        </Card>
      )}
      <div className="space-y-3">
        {(data || []).map((c) => (
          <Card key={c.id} className="p-4 flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <StatusPill status={c.status} />
                <span className="text-xs font-mono text-mute">{c.platform} · {c.content_type}</span>
              </div>
              <Link href={`/studio/${c.id}`} className="font-serif text-lg block mt-1 hover:text-tennis">{c.angle}</Link>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => exportItem(c.id)} disabled={busy === c.id}>
                {busy === c.id ? "…" : "Export bundle"}
              </Button>
              <Button onClick={() => publish(c.id)}>Mark published</Button>
            </div>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
