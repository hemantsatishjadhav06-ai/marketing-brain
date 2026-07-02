"use client";

import useSWR from "swr";
import { AppShell } from "@/components/AppShell";
import { Card, PageHeader, StatusPill } from "@/components/ui";
import { apiFetcher } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function Page() {
  const { data } = useSWR<Job[]>("/jobs", apiFetcher, { refreshInterval: 4000 });
  return (
    <AppShell>
      <PageHeader title="Jobs" description="Every background job the system has run, freshest first. Updates every 4 s." />
      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-panel2 text-mute font-mono text-xs">
            <tr>
              <th className="text-left p-3 w-24">Status</th>
              <th className="text-left p-3 w-44">Type</th>
              <th className="text-left p-3">Brand</th>
              <th className="text-right p-3 w-24">$</th>
              <th className="text-right p-3 w-24">Progress</th>
              <th className="text-right p-3 w-44">Created</th>
            </tr>
          </thead>
          <tbody>
            {(data || []).map((j) => (
              <tr key={j.id} className="border-t border-line">
                <td className="p-3"><StatusPill status={j.status} /></td>
                <td className="p-3 font-mono text-xs">{j.type}</td>
                <td className="p-3 font-mono text-xs">{j.brand_id || "—"}</td>
                <td className="p-3 text-right font-mono">${(j.cost_usd ?? 0).toFixed(4)}</td>
                <td className="p-3 text-right font-mono">{(j.progress ?? 0).toFixed(0)}%</td>
                <td className="p-3 text-right text-xs text-mute">{new Date(j.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {!data?.length && (
              <tr><td colSpan={6} className="p-10 text-center text-mute">No jobs yet.</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </AppShell>
  );
}
