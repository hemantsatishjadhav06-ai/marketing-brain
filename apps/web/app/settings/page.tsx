"use client";

import useSWR from "swr";
import { AppShell } from "@/components/AppShell";
import { Card, PageHeader } from "@/components/ui";
import { apiFetcher } from "@/lib/api";
import type { Brand, Me, CostMeter as CM } from "@/lib/types";

export default function Page() {
  const { data: me } = useSWR<Me>("/auth/me", apiFetcher);
  const { data: brands } = useSWR<Brand[]>("/brands", apiFetcher);
  const { data: cost } = useSWR<CM>("/orgs/me/cost", apiFetcher);

  return (
    <AppShell>
      <PageHeader title="Settings" description="Org · brands · cost cap · roles. Brand brain is on its own page." />
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
        <Card className="p-5 lg:col-span-2">
          <div className="text-xs font-mono text-mute mb-3">BRANDS</div>
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
