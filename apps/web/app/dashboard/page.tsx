"use client";

import useSWR from "swr";
import { Card, PageHeader, StatusPill } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import { apiFetcher } from "@/lib/api";
import type { Brand, Job, CostMeter as CM } from "@/lib/types";

export default function DashboardPage() {
  const { data: brands } = useSWR<Brand[]>("/brands", apiFetcher);
  const { data: jobs } = useSWR<Job[]>("/jobs", apiFetcher, { refreshInterval: 5000 });
  const { data: cost } = useSWR<CM>("/orgs/me/cost", apiFetcher, { refreshInterval: 30000 });

  return (
    <AppShell>
      <PageHeader
        title="Dashboard"
        description="Single pane for the whole content operation."
      />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card className="p-4">
          <div className="text-xs text-mute font-mono">BRANDS</div>
          <div className="font-serif text-3xl mt-1">{brands?.length ?? "—"}</div>
          <div className="text-xs text-mute mt-1">isolated sport verticals</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-mute font-mono">JOBS (24h)</div>
          <div className="font-serif text-3xl mt-1">{jobs?.length ?? "—"}</div>
          <div className="text-xs text-mute mt-1">queued + running + done</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-mute font-mono">MTD SPEND</div>
          <div className="font-serif text-3xl mt-1">${cost?.spent_usd.toFixed(2) ?? "0.00"}</div>
          <div className="text-xs text-mute mt-1">of ${cost?.cap_usd.toFixed(0) ?? "—"} cap</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-mute font-mono">PHASE</div>
          <div className="font-serif text-3xl mt-1">0 / 3</div>
          <div className="text-xs text-mute mt-1">foundation shipped</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-5">
          <div className="text-xs text-mute font-mono mb-3">RECENT JOBS</div>
          {(!jobs || jobs.length === 0) && (
            <div className="text-mute text-sm">No jobs yet. Phase 1 will wire up the queue end-to-end.</div>
          )}
          <ul className="space-y-2">
            {(jobs || []).slice(0, 10).map((j) => (
              <li key={j.id} className="flex items-center justify-between text-sm">
                <span className="font-mono text-xs text-mute truncate">{j.type}</span>
                <StatusPill status={j.status} />
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-5">
          <div className="text-xs text-mute font-mono mb-3">PHASE 0 — WHAT'S LIVE</div>
          <ul className="text-sm space-y-2 text-mute">
            <li>✓ Monorepo: <span className="text-ink">apps/api · apps/web · docs · packages/shared</span></li>
            <li>✓ Docker Compose: <span className="text-ink">postgres · redis · api · worker · web</span></li>
            <li>✓ FastAPI + SQLAlchemy 2.0 + Alembic + JWT auth + RBAC</li>
            <li>✓ Brand-scoped models + <span className="text-ink">no_cross_brand</span> guard + pytest</li>
            <li>✓ Cost guard (org monthly cap → block LLM/media)</li>
            <li>✓ Single LLM gateway (OpenRouter) + swappable media interface (fal)</li>
            <li>✓ Short Video Agent absorbs V1 — sub-type <span className="text-ink">product_video</span></li>
            <li>✓ Next.js 15 shell · 15 routes wired · dark cockpit theme</li>
            <li>✓ 8 docs in <span className="text-ink">/docs</span> · AGENTS.md updated</li>
          </ul>
          <div className="text-xs text-mute mt-4 font-mono">
            → Phase 1 next: scoring engine · calendar agent · 30-day grid · Static/Blog agents · approvals · asset library.
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
