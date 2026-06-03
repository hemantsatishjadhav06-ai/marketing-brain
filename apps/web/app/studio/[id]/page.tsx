"use client";

import { useParams } from "next/navigation";
import useSWR from "swr";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, PageHeader, StatusPill } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";

type Variant = { id: string; label: string; payload: any };
type Review = {
  id: string;
  scores: Record<string, number>;
  weighted_total: number;
  passed: boolean;
  blocking_issues: string[];
  fixes: string[];
  reviewer: string;
  created_at: string;
};
type Item = {
  id: string;
  brand_id: string;
  platform: string;
  content_type: string;
  status: string;
  angle: string;
  agent_name: string;
  payload: any;
  variants: Variant[];
  reviews: Review[];
  created_at: string;
};

function Caption({ payload }: { payload: any }) {
  const fields: [string, any][] = [];
  for (const k of ["headline", "title", "subject_line", "preheader", "caption", "cta"]) {
    if (payload?.[k]) fields.push([k, payload[k]]);
  }
  if (!fields.length) return null;
  return (
    <Card className="p-4">
      <div className="text-xs font-mono text-mute mb-3">CAPTION / COPY</div>
      <div className="space-y-2">
        {fields.map(([k, v]) => (
          <div key={k}>
            <div className="text-[10px] font-mono text-mute uppercase">{k.replace("_", " ")}</div>
            <div className="text-sm whitespace-pre-wrap">{String(v)}</div>
          </div>
        ))}
        {payload.hashtags?.length > 0 && (
          <div>
            <div className="text-[10px] font-mono text-mute uppercase">hashtags</div>
            <div className="text-sm text-tennis">{payload.hashtags.join(" ")}</div>
          </div>
        )}
      </div>
    </Card>
  );
}

function Media({ payload }: { payload: any }) {
  if (payload?.image_url) {
    return (
      <Card className="p-2">
        <img src={payload.image_url} alt="" className="w-full rounded-xl" />
      </Card>
    );
  }
  if (payload?.video_url) {
    return (
      <Card className="p-2">
        <video controls src={payload.video_url} className="w-full rounded-xl" />
      </Card>
    );
  }
  if (Array.isArray(payload?.slides) && payload.slides.length > 0) {
    return (
      <Card className="p-2">
        <div className="grid grid-cols-2 gap-2">
          {payload.slides.map((s: any) => (
            <div key={s.index} className="relative">
              <img src={s.image_url} alt="" className="w-full rounded-lg" />
              <span className="absolute top-1 right-1 text-[10px] font-mono bg-bg/70 px-1 rounded">{s.index}/{payload.slides.length}</span>
            </div>
          ))}
        </div>
      </Card>
    );
  }
  if (Array.isArray(payload?.sections)) {
    return (
      <Card className="p-5 space-y-4">
        {payload.title && <h1 className="font-serif text-3xl">{payload.title}</h1>}
        {payload.meta_description && <div className="text-xs text-mute italic">{payload.meta_description}</div>}
        {payload.sections.map((s: any, i: number) => (
          <div key={i}>
            <h2 className="font-serif text-xl mt-3 mb-1">{s.h2}</h2>
            <p className="text-sm text-ink/90 whitespace-pre-wrap">{s.body}</p>
          </div>
        ))}
      </Card>
    );
  }
  if (Array.isArray(payload?.blocks)) {
    return (
      <Card className="p-5 space-y-3">
        {payload.blocks.map((b: any, i: number) => {
          if (b.type === "headline") return <h1 key={i} className="font-serif text-2xl">{b.text}</h1>;
          if (b.type === "cta")
            return <div key={i}><a className="inline-block px-4 py-2 rounded-xl bg-tennis text-black font-medium" href={b.url || "#"}>{b.text}</a></div>;
          return <p key={i} className="text-sm">{b.text}</p>;
        })}
      </Card>
    );
  }
  return <Card className="p-6 text-mute text-sm">No media preview.</Card>;
}

export default function Page() {
  const params = useParams<{ id: string }>();
  const id = params?.id as string;
  const { data, mutate } = useSWR<Item>(id ? `/content/${id}` : null, apiFetcher);

  async function runCritic() {
    if (!data) return;
    try {
      await api(`/brands/${data.brand_id}/reviews/${data.id}/run`, { method: "POST" });
      toast.success("Critic finished");
      mutate();
    } catch (e: any) { toast.error(e.message); }
  }

  async function transition(to: string) {
    if (!data) return;
    try {
      await api(`/content/${data.id}/transition?to=${to}`, { method: "POST" });
      mutate();
    } catch (e: any) { toast.error(e.message); }
  }

  async function exportBundle() {
    if (!data) return;
    try {
      const r = await api<{ url: string; bytes: number }>(`/publishing/export/${data.id}`, { method: "POST" });
      toast.success(`Bundle exported · ${(r.bytes / 1024).toFixed(0)} KB`);
      window.open(r.url, "_blank");
    } catch (e: any) { toast.error(e.message); }
  }

  if (!data) return <AppShell><Card className="p-8">Loading…</Card></AppShell>;

  return (
    <AppShell>
      <PageHeader
        title={data.angle.slice(0, 80) || "Untitled"}
        description={
          <span className="flex gap-2 items-center">
            <StatusPill status={data.status} />
            <span className="font-mono text-xs">{data.platform} · {data.content_type} · {data.agent_name}</span>
          </span>
        }
        action={
          <div className="flex gap-2">
            <Button variant="outline" onClick={runCritic}>Run critic</Button>
            {data.status === "drafted" && <Button onClick={() => transition("under_review")}>Send to review</Button>}
            {data.status === "under_review" && <Button onClick={() => transition("approved")}>Approve</Button>}
            <Button variant="ghost" onClick={exportBundle}>Export bundle</Button>
          </div>
        }
      />
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
        <div className="space-y-4">
          <Media payload={data.payload} />
          <Caption payload={data.payload} />
        </div>
        <div className="space-y-4">
          <Card className="p-4">
            <div className="text-xs font-mono text-mute mb-3">CRITIC HISTORY</div>
            {data.reviews.length === 0 && <div className="text-sm text-mute">No reviews yet — click "Run critic".</div>}
            <div className="space-y-3">
              {data.reviews.map((r) => (
                <div key={r.id} className="border-t border-line pt-3 first:border-0 first:pt-0">
                  <div className="flex items-center justify-between">
                    <span className={`font-mono text-xs ${r.passed ? "text-emerald-400" : "text-red-400"}`}>
                      {r.weighted_total.toFixed(1)} {r.passed ? "✓" : "✗"}
                    </span>
                    <span className="text-[10px] text-mute">{new Date(r.created_at).toLocaleString()}</span>
                  </div>
                  {Object.keys(r.scores).length > 0 && (
                    <div className="mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
                      {Object.entries(r.scores).map(([k, v]) => (
                        <div key={k} className="flex justify-between"><span className="text-mute font-mono">{k}</span><span>{v}</span></div>
                      ))}
                    </div>
                  )}
                  {r.blocking_issues.length > 0 && (
                    <ul className="mt-2 text-xs text-red-300 list-disc list-inside">
                      {r.blocking_issues.map((b, i) => <li key={i}>{b}</li>)}
                    </ul>
                  )}
                  {r.fixes.length > 0 && (
                    <div className="mt-2">
                      <div className="text-[10px] font-mono text-mute uppercase">fixes</div>
                      <ul className="text-xs list-disc list-inside text-mute">{r.fixes.map((f, i) => <li key={i}>{f}</li>)}</ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-xs font-mono text-mute mb-3">VARIANTS</div>
            {data.variants.map((v) => <div key={v.id} className="text-xs font-mono text-mute">· {v.label}</div>)}
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
