"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type IntegrationStatus = {
  magento: { connected: boolean; base_url: string | null; token_set: boolean };
};

type SyncResult = {
  categories_synced: number;
  leaf_categories_with_products: number;
  products_upserted: number;
  skus_seen: number;
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const { data, mutate } = useSWR<IntegrationStatus>(
    brandId ? `/brands/${brandId}/integrations` : null,
    apiFetcher,
  );

  const [baseUrl, setBaseUrl] = useState("https://tennisoutlet.in");
  const [token, setToken] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data?.magento?.base_url) setBaseUrl(data.magento.base_url);
  }, [data?.magento?.base_url]);

  async function connect() {
    if (!brandId) return;
    if (!baseUrl.startsWith("http")) { toast.error("Base URL must start with http(s)://"); return; }
    if (token.length < 10) { toast.error("Token looks too short"); return; }
    setBusy(true);
    try {
      await api(`/brands/${brandId}/integrations/magento/connect`, {
        method: "POST",
        body: JSON.stringify({ base_url: baseUrl, token }),
      });
      toast.success("Magento connected · token encrypted at rest");
      setToken("");
      mutate();
    } catch (e: any) { toast.error(e.message); }
    finally { setBusy(false); }
  }

  async function sync() {
    if (!brandId) return;
    setSyncing(true);
    try {
      const r = await api<SyncResult>(`/brands/${brandId}/integrations/magento/sync`, { method: "POST" });
      toast.success(`Synced ${r.categories_synced} categories · ${r.products_upserted} products`);
      mutate();
    } catch (e: any) { toast.error(e.message); }
    finally { setSyncing(false); }
  }

  async function disconnect() {
    if (!brandId) return;
    if (!confirm("Disconnect Magento for this brand? (Synced products stay.)")) return;
    try {
      await api(`/brands/${brandId}/integrations/magento`, { method: "DELETE" });
      toast.success("Magento disconnected");
      mutate();
    } catch (e: any) { toast.error(e.message); }
  }

  return (
    <AppShell>
      <PageHeader
        title="Integrations"
        description="Connect your stores so the cockpit speaks real product data. Tokens are encrypted at rest (Fernet keyed off JWT_SECRET) and never echoed back."
      />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && (
        <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
          <Card className="p-6">
            <div className="flex items-center gap-3">
              <div className="size-10 grid place-items-center rounded-lg accent-bg font-mono text-lg">M</div>
              <div>
                <div className="display text-xl">Magento 2</div>
                <div className="text-mute text-xs">REST API · per-brand token · category + product sync</div>
              </div>
              <span className={`ml-auto text-xs font-mono px-2 py-1 rounded ${data?.magento?.connected ? "bg-good/15 text-good" : "bg-panel2 text-mute"}`}>
                {data?.magento?.connected ? "✓ connected" : "not connected"}
              </span>
            </div>

            <div className="mt-6 space-y-3">
              <div>
                <label className="text-[10px] uppercase tracking-widest text-mute font-mono">Magento store base URL</label>
                <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://tennisoutlet.in" />
                <div className="text-[11px] text-mute mt-1">Without trailing slash. The connector hits {`${baseUrl}/rest/V1/...`}</div>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-mute font-mono">Admin / integration token</label>
                <Input value={token} onChange={(e) => setToken(e.target.value)} type="password"
                       placeholder={data?.magento?.connected ? "•••••••••• (replace)" : "375syepu5xo13ejewk8mqekj100qxlnr"} />
                <div className="text-[11px] text-mute mt-1">
                  Magento → System → Extensions → Integrations → New Integration → Access Token.
                  Encrypted with Fernet before it touches the DB.
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={connect} disabled={busy || !token}>
                  {busy ? "Saving…" : data?.magento?.connected ? "Update credentials" : "Connect"}
                </Button>
                <Button variant="outline" onClick={sync} disabled={!data?.magento?.connected || syncing}>
                  {syncing ? "Syncing…" : "Sync categories + products now"}
                </Button>
                {data?.magento?.connected && (
                  <Button variant="ghost" onClick={disconnect}>Disconnect</Button>
                )}
              </div>
            </div>
          </Card>

          <div className="space-y-3">
            <Card className="p-4">
              <div className="text-[10px] font-mono text-mute uppercase tracking-widest mb-2">what gets synced</div>
              <ul className="text-xs space-y-1.5 text-ink2">
                <li>· <b>Categories</b> → cached on BrandBrain.content_templates.magento_categories</li>
                <li>· <b>Products</b> → upserted into the Products table by SKU (brand-scoped)</li>
                <li>· <b>Primary image</b> → first non-disabled media_gallery_entry</li>
                <li>· <b>Price, status, type, category_ids</b> → kept in Product.attributes</li>
              </ul>
            </Card>
            <Card className="p-4">
              <div className="text-[10px] font-mono text-mute uppercase tracking-widest mb-2">where it shows up</div>
              <ul className="text-xs space-y-1.5 text-ink2">
                <li>· <Link href="/create" className="accent-text hover:underline">Create</Link> → Category dropdown filters Products</li>
                <li>· Selected product shows thumbnail + price + SKU inline</li>
                <li>· Carousel / Blog / Ads tabs accept up to 5 products for comparison</li>
                <li>· <Link href="/products" className="accent-text hover:underline">Products</Link> page lists everything you've synced</li>
              </ul>
            </Card>
            <Card className="p-4 text-[11px] text-mute">
              <div className="font-mono text-[10px] mb-2 uppercase tracking-widest">soon</div>
              Shopify, Klaviyo (already in publish targets), Stripe billing data, GA4 (already in analytics pull).
              All flow into this page so a marketing-agency owner has one place to wire each client's stack.
            </Card>
          </div>
        </div>
      )}
    </AppShell>
  );
}
