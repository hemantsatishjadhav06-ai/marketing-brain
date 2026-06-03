"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Card, PageHeader } from "@/components/ui";
import { apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Asset = {
  id: string;
  kind: string;
  url: string;
  mime: string;
  width: number;
  height: number;
  duration_s: number;
  content_item_id: string | null;
  created_at: string;
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [kind, setKind] = useState("");
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);
  const key = brandId ? `/brands/${brandId}/assets${kind ? `?kind=${kind}` : ""}` : null;
  const { data } = useSWR<Asset[]>(key, apiFetcher);

  return (
    <AppShell>
      <PageHeader title="Library" description="Every asset every agent has produced for this brand." />
      <div className="flex gap-2 mb-4">
        <select className="rounded-lg bg-panel2 border border-line px-3 py-1.5 text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">All kinds</option>
          {["image", "carousel", "video", "audio", "blog", "caption", "hashtags", "thumbnail"].map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <span className="text-xs font-mono text-mute ml-auto self-center">{data?.length ?? 0} assets</span>
      </div>
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {(data || []).map((a) => (
          <Card key={a.id} className="overflow-hidden">
            {a.kind === "video" ? (
              <video src={a.url} className="w-full aspect-square object-cover" muted />
            ) : (
              <img src={a.url} alt="" className="w-full aspect-square object-cover" />
            )}
            <div className="p-2 text-[10px] font-mono text-mute flex items-center justify-between">
              <span>{a.kind}</span>
              {a.content_item_id && <Link href={`/studio/${a.content_item_id}`} className="text-tennis hover:underline">item</Link>}
            </div>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
