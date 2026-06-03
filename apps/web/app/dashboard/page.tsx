"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Card, PageHeader, StatusPill } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import { apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";
import type { Brand, Job, CostMeter as CM } from "@/lib/types";

type Idea = { id: string; title: string; score: number; platform: string };
type Pending = { id: string; angle: string; platform: string };
type CalEntry = { id: string; date: string };

export default function DashboardPage() {
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const { data: brands } = useSWR<Brand[]>("/brands", apiFetcher);
  const { data: jobs } = useSWR<Job[]>("/jobs", apiFetcher, { refreshInterval: 5000 });
  const { data: cost } = useSWR<CM>("/orgs/me/cost", apiFetcher, { refreshInterval: 30000 });
  const { data: ideas } = useSWR<Idea[]>(brandId ? `/brands/${brandId}/ideas?limit=5` : null, apiFetcher);
  const { data: reviews } = useSWR<Pending[]>(brandId ? `/brands/${brandId}/reviews/pending?limit=5` : null, apiFetcher);
  const { data: cal } = useSWR<CalEntry[]>(brandId ? `/brands/${brandId}/calendar` : null, apiFetcher);

  return (
    <AppShell>
      <PageHeader title="Dashboard" description="Single pane for the whole content operation." />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card className="p-4">
          <div className="text-xs text-mute font-mono">BRANDS</div>
          <div className="font-serif text-3xl mt-1">{brands?.length ?? "—"}</div>
          <div className="text-xs text-mute mt-1">isolated sport verticals</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-mute font-mono">CALENDAR ENTRIES</div>
          <div className="font-serif text-3xl mt-1">{cal?.length ?? "—"}</div>
          <div className="text-xs text-mute mt-1">scheduled in current plan</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-mute font-mono">MTD SPEND</div>
          <div className="font-serif text-3xl mt-1">${cost?.spent_usd?.toFixed(2) ?? "0.00"}</div>
          <div className="text-xs text-mute mt-1">of ${cost?.cap_usd?.toFixed(0) ?? "—"} cap</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-mute font-mono">REVIEW QUEUE</div>
          <div className="font-serif text-3xl mt-1">{reviews?.length ?? 0}</div>
          <div className="text-xs text-mute mt-1">drafts awaiting approval</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs text-mute font-mono">TOP-SCORED IDEAS</div>
            <Link href="/ideas" className="text-xs text-tennis hover:underline">view all →</Link>
          </div>
          {(!ideas || ideas.length === 0) && <div className="text-mute text-sm">No ideas yet — generate from the Ideas page.</div>}
          <ul className="space-y-2">
            {(ideas || []).slice(0, 5).map((i) => (
              <li key={i.id} className="flex items-center gap-3 text-sm">
                <span className="font-mono text-tennis w-12 text-right">{i.score.toFixed(0)}</span>
                <span className="font-mono text-xs text-mute w-20">{i.platform}</span>
                <span className="truncate flex-1">{i.title}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs text-mute font-mono">RECENT JOBS</div>
            <Link href="/jobs" className="text-xs text-tennis hover:underline">view all →</Link>
          </div>
          {(!jobs || jobs.length === 0) && <div className="text-mute text-sm">No jobs yet.</div>}
          <ul className="space-y-2">
            {(jobs || []).slice(0, 8).map((j) => (
              <li key={j.id} className="flex items-center justify-between text-sm">
                <span className="font-mono text-xs text-mute truncate">{j.type}</span>
                <StatusPill status={j.status} />
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="p-5 mt-4">
        <div className="text-xs text-mute font-mono mb-2">WHAT'S LIVE</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div>
            <div className="font-serif text-base mb-1">Foundation</div>
            <ul className="text-mute space-y-1 text-xs">
              <li>✓ FastAPI + SQLAlchemy + Alembic</li>
              <li>✓ Brand-scoped models + cross-sport guard</li>
              <li>✓ JWT auth + 6-role RBAC</li>
              <li>✓ Cost guard · one LLM gateway · swappable media + storage</li>
            </ul>
          </div>
          <div>
            <div className="font-serif text-base mb-1">Phase 1+2 — Live</div>
            <ul className="text-mute space-y-1 text-xs">
              <li>✓ Scoring engine + ScoringRun history</li>
              <li>✓ Idea Mill agent + 30-day Calendar agent</li>
              <li>✓ Static Post · Carousel · Blog · Email · Short Video agents</li>
              <li>✓ Critic v2 (regex hard-gate + LLM rubric)</li>
              <li>✓ Reviews · Studio · Library · Publishing (export bundle)</li>
              <li>✓ Repurpose agent · Analytics ingest + dashboard</li>
            </ul>
          </div>
          <div>
            <div className="font-serif text-base mb-1">Phase 3 — Roadmap</div>
            <ul className="text-mute space-y-1 text-xs">
              <li>· Native publishing (Meta/X/LinkedIn/YouTube/TikTok)</li>
              <li>· Live analytics pulls (GA4 + per-platform)</li>
              <li>· Brand brain refinement loop from performance</li>
              <li>· White-label theming + billing</li>
            </ul>
          </div>
        </div>
      </Card>
    </AppShell>
  );
}
