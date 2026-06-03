"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, PageHeader, StatusPill } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Pending = {
  id: string;
  platform: string;
  content_type: string;
  angle: string;
  status: string;
  agent_name: string;
  created_at: string;
  last_review: {
    weighted_total: number;
    passed: boolean;
    scores: Record<string, number>;
    blocking_issues: string[];
  } | null;
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

  const key = brandId ? `/brands/${brandId}/reviews/pending` : null;
  const { data, mutate } = useSWR<Pending[]>(key, apiFetcher);

  async function run(id: string) {
    if (!brandId) return;
    setBusy(id);
    try {
      const r = await api<{ weighted_total: number; passed: boolean }>(
        `/brands/${brandId}/reviews/${id}/run`,
        { method: "POST" }
      );
      toast.success(`Critic: ${r.weighted_total} ${r.passed ? "✓" : "✗"}`);
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(null);
    }
  }
  async function approve(id: string) {
    if (!brandId) return;
    setBusy(id);
    try {
      await api(`/brands/${brandId}/reviews/${id}/approve`, { method: "POST" });
      toast.success("Approved");
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(null);
    }
  }
  async function reject(id: string) {
    if (!brandId) return;
    const reason = prompt("Reason for rejection?") || "rejected";
    setBusy(id);
    try {
      await api(`/brands/${brandId}/reviews/${id}/reject?reason=${encodeURIComponent(reason)}`, { method: "POST" });
      toast.success("Rejected");
      mutate();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(null);
    }
  }

  const [selected, setSelected] = useState<Set<string>>(new Set());
  function toggle(id: string) {
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  }
  async function bulkApprove() {
    if (!brandId || selected.size === 0) return;
    setBusy("bulk");
    let ok = 0, fail = 0;
    for (const id of selected) {
      try { await api(`/brands/${brandId}/reviews/${id}/approve`, { method: "POST" }); ok++; }
      catch { fail++; }
    }
    setSelected(new Set());
    setBusy(null);
    toast.success(`Approved ${ok}${fail ? ` (${fail} failed)` : ""}`);
    mutate();
  }

  return (
    <AppShell>
      <PageHeader
        title="Reviews"
        description="Drafts awaiting critic + human approval. The Critic runs cross-sport hard gate first, then the LLM rubric."
        action={selected.size > 0 ? (
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-mute">{selected.size} selected</span>
            <Button variant="outline" onClick={() => setSelected(new Set())}>Clear</Button>
            <Button onClick={bulkApprove} disabled={busy === "bulk"}>{busy === "bulk" ? "…" : `Approve ${selected.size}`}</Button>
          </div>
        ) : undefined}
      />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && data && data.length === 0 && (
        <Card className="p-10 text-center">
          <div className="font-serif text-2xl">Nothing in the queue</div>
          <div className="text-mute text-sm mt-2">Draft a calendar entry to populate the review queue.</div>
        </Card>
      )}
      <div className="space-y-3">
        {(data || []).map((c) => (
          <Card key={c.id} className="p-4">
            <div className="flex items-start gap-4">
              <input
                type="checkbox"
                checked={selected.has(c.id)}
                onChange={() => toggle(c.id)}
                className="size-4 mt-2 accent-tennis"
                title="Select for bulk action"
              />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <StatusPill status={c.status} />
                  <span className="text-xs font-mono text-mute">{c.platform} · {c.content_type} · {c.agent_name}</span>
                </div>
                <Link href={`/studio/${c.id}`} className="font-serif text-xl mt-1 block hover:text-tennis">{c.angle}</Link>
                {c.last_review && (
                  <div className="mt-2 text-xs">
                    <span className={`font-mono ${c.last_review.passed ? "text-emerald-400" : "text-red-400"}`}>
                      critic: {c.last_review.weighted_total.toFixed(1)} {c.last_review.passed ? "✓" : "✗"}
                    </span>
                    {c.last_review.blocking_issues.length > 0 && (
                      <span className="ml-2 text-red-400">{c.last_review.blocking_issues.join(" · ")}</span>
                    )}
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => run(c.id)} disabled={busy === c.id}>
                  {busy === c.id ? "…" : "Run critic"}
                </Button>
                <Button onClick={() => approve(c.id)} disabled={busy === c.id}>Approve</Button>
                <Button variant="ghost" onClick={() => reject(c.id)} disabled={busy === c.id}>Reject</Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
