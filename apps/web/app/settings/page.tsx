"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import type { Brand, Me, CostMeter as CM } from "@/lib/types";

type Theme = {
  brand_name: string;
  accent_color: string;
  logo_url: string;
  hide_powered_by: boolean;
};
type Billing = { configured: boolean; plan?: string; status?: string };

export default function Page() {
  const { data: me } = useSWR<Me>("/auth/me", apiFetcher);
  const { data: brands } = useSWR<Brand[]>("/brands", apiFetcher);
  const { data: cost } = useSWR<CM>("/orgs/me/cost", apiFetcher);
  const { data: theme, mutate: mutateTheme } = useSWR<Theme>("/orgs/me/theme", apiFetcher);
  const { data: billing } = useSWR<Billing>("/billing/summary", apiFetcher);

  const [name, setName] = useState("");
  const [color, setColor] = useState("");
  const [logo, setLogo] = useState("");
  const [hide, setHide] = useState(false);

  useEffect(() => {
    if (!theme) return;
    setName(theme.brand_name || "");
    setColor(theme.accent_color || "#CCFF00");
    setLogo(theme.logo_url || "");
    setHide(!!theme.hide_powered_by);
  }, [theme]);

  async function saveTheme() {
    try {
      await api("/orgs/me/theme", {
        method: "PUT",
        body: JSON.stringify({ brand_name: name, accent_color: color, logo_url: logo, hide_powered_by: hide }),
      });
      toast.success("Theme saved");
      mutateTheme();
    } catch (e: any) { toast.error(e.message); }
  }

  async function startCheckout() {
    try {
      const r = await api<{ url: string }>("/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ success_url: window.location.href, cancel_url: window.location.href }),
      });
      window.location.href = r.url;
    } catch (e: any) { toast.error(e.message); }
  }

  return (
    <AppShell>
      <PageHeader title="Settings" description="Org · brands · cost cap · billing · white-label theme · publish targets." />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-5">
          <div className="text-xs font-mono text-mute mb-3">YOUR USER</div>
          <div className="text-sm">{me?.email}</div>
          <div className="text-xs font-mono text-mute mt-1">role · {me?.role}</div>
          <div className="text-xs font-mono text-mute">org · {me?.org_id}</div>
        </Card>
        <Card className="p-5">
          <div className="text-xs font-mono text-mute mb-3">MTD COST GUARD</div>
          <div className="font-serif text-3xl">${cost?.spent_usd?.toFixed(2) ?? "0.00"}</div>
          <div className="text-xs font-mono text-mute mt-1">of ${cost?.cap_usd?.toFixed(0) ?? "—"} cap · {cost?.pct_used?.toFixed(0) ?? 0}% used</div>
          <div className="mt-3 h-2 rounded-full bg-panel2 overflow-hidden">
            <div className="h-full bg-tennis" style={{ width: `${Math.min(100, cost?.pct_used ?? 0)}%` }} />
          </div>
        </Card>

        <Card className="p-5">
          <div className="text-xs font-mono text-mute mb-3">WHITE-LABEL THEME</div>
          <div className="space-y-2">
            <Input placeholder="Brand name" value={name} onChange={(e) => setName(e.target.value)} />
            <div className="flex gap-2 items-center">
              <input type="color" value={color || "#CCFF00"} onChange={(e) => setColor(e.target.value)} className="size-10 rounded-lg" />
              <Input placeholder="Accent #hex" value={color} onChange={(e) => setColor(e.target.value)} />
            </div>
            <Input placeholder="Logo URL (https://…)" value={logo} onChange={(e) => setLogo(e.target.value)} />
            <label className="flex items-center gap-2 text-sm text-mute">
              <input type="checkbox" checked={hide} onChange={(e) => setHide(e.target.checked)} />
              Hide "powered by" footer
            </label>
            <Button onClick={saveTheme} className="mt-2">Save theme</Button>
          </div>
        </Card>

        <Card className="p-5">
          <div className="text-xs font-mono text-mute mb-3">BILLING</div>
          <div className="text-sm">
            Plan: <span className="font-mono text-tennis">{billing?.plan || "developer"}</span>
          </div>
          {billing?.status && <div className="text-xs font-mono text-mute mt-1">status · {billing.status}</div>}
          <div className="text-xs text-mute mt-1">
            {billing?.configured ? "Stripe connected." : "Dev mode — set STRIPE_SECRET_KEY to enable real billing."}
          </div>
          <Button onClick={startCheckout} className="mt-3">Manage billing</Button>
        </Card>

        <Card className="p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-mono text-mute">BRANDS</div>
            <Link href="/settings/publish-targets" className="text-xs text-tennis hover:underline">Manage publish targets →</Link>
          </div>
          <div className="space-y-2">
            {(brands || []).map((b) => (
              <div key={b.id} className="flex items-center justify-between text-sm border-b border-line last:border-0 pb-2">
                <div className="flex items-center gap-3">
                  <span className="size-3 rounded-sm" style={{ background: b.accent_color || "#CCFF00" }} />
                  <span>{b.name}</span>
                  <span className="font-mono text-mute text-xs">· {b.sport}</span>
                </div>
                <span className="text-mute text-xs font-mono">{b.timezone} · {b.active ? "active" : "off"}</span>
              </div>
            ))}
            {!brands?.length && <div className="text-mute text-sm">No brands yet.</div>}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
