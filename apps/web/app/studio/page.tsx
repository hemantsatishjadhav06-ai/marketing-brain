"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Card, PageHeader, StatusPill } from "@/components/ui";
import { apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Row = {
  id: string;
  platform: string;
  content_type: string;
  status: string;
  angle: string;
  agent_name: string;
  created_at: string;
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);
  const { data } = useSWR<Row[]>(brandId ? `/content?brand_id=${brandId}` : null, apiFetcher);

  return (
    <AppShell>
      <PageHeader title="Studio" description="Every drafted, reviewed, approved or published content item — one click into the editor." />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && data && data.length === 0 && (
        <Card className="p-10 text-center">
          <div className="font-serif text-2xl">No content yet</div>
          <div className="text-mute text-sm mt-2">Draft entries from the Calendar to populate the Studio.</div>
        </Card>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {(data || []).map((c) => (
          <Link key={c.id} href={`/studio/${c.id}`} className="block">
            <Card className="p-4 hover:bg-panel2/40 transition">
              <div className="flex items-center justify-between">
                <StatusPill status={c.status} />
                <span className="text-xs font-mono text-mute">{c.platform} · {c.content_type}</span>
              </div>
              <div className="font-serif text-lg mt-2 line-clamp-3">{c.angle}</div>
              <div className="text-xs font-mono text-mute mt-2">{c.agent_name}</div>
            </Card>
          </Link>
        ))}
      </div>
    </AppShell>
  );
}
