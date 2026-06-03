"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Card, PageHeader } from "@/components/ui";
import { getSelectedBrand } from "@/lib/brandStore";

const PILLARS = [
  { name: "Demographics", lines: ["age 22–45", "weekend players", "intermediate–advanced"] },
  { name: "Buying triggers", lines: ["new season", "broken string", "upgrade after league results"] },
  { name: "Content cues", lines: ["honest gear takes", "drills that work in 20 min", "pro-level fundamentals"] },
  { name: "What they ignore", lines: ["hype influencer takes", "vague \"best ever\" claims", "off-sport comparisons"] },
];

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  return (
    <AppShell>
      <PageHeader
        title="Audience"
        description="The personas the Idea Mill + Critic carry around in their heads."
      />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {PILLARS.map((p) => (
            <Card key={p.name} className="p-5">
              <div className="text-xs font-mono text-mute">{p.name.toUpperCase()}</div>
              <ul className="mt-3 space-y-1 text-sm">
                {p.lines.map((l) => <li key={l} className="text-ink">· {l}</li>)}
              </ul>
            </Card>
          ))}
          <Card className="p-5 md:col-span-2 text-mute text-sm">
            Editable personas (with per-platform affinity scores) land in Phase 3.
            Today the audience model is templated per sport vertical.
          </Card>
        </div>
      )}
    </AppShell>
  );
}
