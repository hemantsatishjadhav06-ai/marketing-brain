"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Sparkles, RefreshCcw } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader, Skeleton } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Product = {
  id: string; sku: string; title: string; description: string;
  category: string; price: number; margin: number;
  image_urls: string[]; status: string;
  is_new: boolean; is_bestseller: boolean; is_dead_stock: boolean; is_discounted: boolean;
};
type Category = { external_id: string; name: string; product_count: number };

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [syncing, setSyncing] = useState(false);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const productsKey = brandId
    ? `/brands/${brandId}/products${category ? `?category=${encodeURIComponent(category)}` : ""}`
    : null;
  const { data, isLoading, mutate } = useSWR<Product[]>(productsKey, apiFetcher);
  const products = Array.isArray(data) ? data : [];
  const filtered = q.trim().length > 0
    ? products.filter((p) =>
        [p.sku, p.title, p.category].some((s) => (s || "").toLowerCase().includes(q.toLowerCase())))
    : products;

  const { data: catsResp } = useSWR<Category[]>(
    brandId ? `/brands/${brandId}/integrations/magento/categories` : null, apiFetcher,
  );
  const categories = Array.isArray(catsResp) ? catsResp.filter((c) => c.product_count > 0).sort((a, b) => a.name.localeCompare(b.name)) : [];

  async function syncNow() {
    if (!brandId) return;
    setSyncing(true);
    try {
      const r = await api<{ products_upserted: number }>(`/brands/${brandId}/integrations/magento/sync`, { method: "POST" });
      toast.success(`Synced ${r.products_upserted} products`);
      mutate();
    } catch (e: any) { toast.error(e.message); }
    finally { setSyncing(false); }
  }

  return (
    <AppShell>
      <PageHeader
        title="Products"
        description="Brand-scoped product catalogue from Magento. Click Generate on any row to fire any agent against that SKU."
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={syncNow} disabled={!brandId || syncing}>
              <RefreshCcw className="size-4" />
              {syncing ? "Syncing…" : "Sync from Magento"}
            </Button>
            <Link href="/settings/integrations" className="text-xs accent-text hover:underline self-center">Configure →</Link>
          </div>
        }
      />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && (
        <>
          <div className="flex flex-wrap gap-2 mb-4">
            <select className="rounded-lg bg-panel2 border hairline px-3 py-1.5 text-sm" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {categories.map((c) => <option key={c.external_id} value={c.name}>{c.name} ({c.product_count})</option>)}
            </select>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search SKU / title…" className="max-w-xs" />
            {(category || q) && <button onClick={() => { setCategory(""); setQ(""); }} className="text-xs text-mute hover:text-ink font-mono px-2 self-center">clear ✕</button>}
            <span className="text-xs font-mono text-mute ml-auto self-center">{filtered.length} products</span>
          </div>

          {isLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {Array.from({ length: 9 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
            </div>
          )}

          {!isLoading && filtered.length === 0 && (
            <Card className="p-10 text-center">
              <div className="font-serif text-2xl">No products yet</div>
              <div className="text-mute text-sm mt-2">
                Connect Magento in <Link href="/settings/integrations" className="accent-text hover:underline">Settings → Integrations</Link>, then click "Sync from Magento".
              </div>
            </Card>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filtered.map((p) => {
              const img = (p.image_urls || [])[0];
              return (
                <Card key={p.id} className="p-3 flex gap-3">
                  {img ? <img src={img} alt="" className="size-24 rounded-lg object-cover bg-bg2" />
                       : <div className="size-24 rounded-lg bg-bg2 grid place-items-center text-mute text-[10px] font-mono">no image</div>}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium line-clamp-2">{p.title}</div>
                    <div className="text-[11px] font-mono text-mute mt-0.5 line-clamp-1">{p.sku} · ${p.price}{p.category ? ` · ${p.category}` : ""}</div>
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {p.is_bestseller && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-good/15 text-good">bestseller</span>}
                      {p.is_new && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-300">new</span>}
                      {p.is_dead_stock && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-red-500/15 text-red-300">dead stock</span>}
                      {p.is_discounted && <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-warn/15 text-warn">discount</span>}
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <Link
                        href={`/create?product_id=${p.id}`}
                        className="inline-flex items-center gap-1 rounded-lg accent-bg px-3 py-1 text-xs font-medium hover:opacity-90"
                      >
                        <Sparkles className="size-3.5" /> Generate
                      </Link>
                      <Link href={`/products/${p.id}/perf`} className="text-[11px] text-mute hover:text-ink">View perf →</Link>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </>
      )}
    </AppShell>
  );
}
