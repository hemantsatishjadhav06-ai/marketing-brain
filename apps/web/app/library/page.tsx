"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { toast } from "sonner";
import { Download } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Card, PageHeader, Skeleton } from "@/components/ui";
import { apiFetcher, getToken } from "@/lib/api";
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

async function downloadAsset(contentItemId: string, assetId: string) {
  const t = getToken();
  const r = await fetch(`/api/content/${contentItemId}/download/asset/${assetId}`, {
    headers: t ? { Authorization: `Bearer ${t}` } : {},
  });
  if (!r.ok) { toast.error(`Download failed (${r.status})`); return; }
  const blob = await r.blob();
  const cd = r.headers.get("content-disposition") || "";
  const m = cd.match(/filename="([^"]+)"/);
  const filename = m ? m[1] : `asset-${assetId}`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
  toast.success("Downloaded");
}

type CategoryRow = { external_id: string; name: string; product_count: number };

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [kind, setKind] = useState("");
  const [category, setCategory] = useState("");
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);
  const params = new URLSearchParams();
  if (kind) params.set("kind", kind);
  if (category) params.set("category", category);
  const qs = params.toString();
  const key = brandId ? `/brands/${brandId}/assets${qs ? `?${qs}` : ""}` : null;
  const { data, isLoading, mutate } = useSWR<Asset[]>(key, apiFetcher, {
    revalidateOnFocus: true, revalidateOnReconnect: true, revalidateOnMount: true,
  });
  const { data: catsResp } = useSWR<CategoryRow[]>(brandId ? `/brands/${brandId}/integrations/magento/categories` : null, apiFetcher);
  const categories = Array.isArray(catsResp) ? catsResp.filter((c) => c.product_count > 0).sort((a, b) => a.name.localeCompare(b.name)) : [];

  return (
    <AppShell>
      <PageHeader title="Library" description="Every asset every agent has produced. Download any single one or open the full content item." />
      <div className="flex flex-wrap gap-2 mb-4">
        <select className="rounded-lg bg-panel2 border hairline px-3 py-1.5 text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">All kinds</option>
          {["image", "carousel", "video", "audio", "blog", "caption", "hashtags", "thumbnail"].map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <select className="rounded-lg bg-panel2 border hairline px-3 py-1.5 text-sm" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.external_id} value={c.name}>{c.name} ({c.product_count})</option>)}
        </select>
        {(kind || category) && (
          <button onClick={() => { setKind(""); setCategory(""); }} className="text-xs text-mute hover:text-ink font-mono px-2 self-center">clear ✕</button>
        )}
        <span className="text-xs font-mono text-mute ml-auto self-center">{data?.length ?? 0} assets</span>
      </div>
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square rounded-xl" />
          ))}
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {(data || []).map((a) => (
          <Card key={a.id} className="overflow-hidden group relative">
            {a.kind === "video" ? (
              <video src={a.url} className="w-full aspect-square object-cover" muted />
            ) : (
              <img src={a.url} alt="" className="w-full aspect-square object-cover" />
            )}
            <button
              onClick={() => a.content_item_id && downloadAsset(a.content_item_id, a.id)}
              disabled={!a.content_item_id}
              className="absolute top-2 right-2 size-8 grid place-items-center rounded-lg glass opacity-0 group-hover:opacity-100 transition disabled:opacity-30"
              title="Download this asset"
            >
              <Download className="size-4" />
            </button>
            <div className="p-2 text-[10px] font-mono text-mute flex items-center justify-between">
              <span>{a.kind}</span>
              {a.content_item_id && <Link href={`/studio/${a.content_item_id}`} className="accent-text hover:underline">item</Link>}
            </div>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
