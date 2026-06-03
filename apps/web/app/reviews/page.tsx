"use client";

import { AppShell } from "@/components/AppShell";
import { Card, PageHeader } from "@/components/ui";

export default function Page() {
  return (
    <AppShell>
      <PageHeader title="Reviews" description="Critic-gated approvals. Score breakdown + fixes. Cross-sport = auto-reject." />
      <Card className="p-8">
        <div className="text-xs font-mono text-mute mb-2">Phase 1</div>
        <div className="font-serif text-2xl mb-2">Lands in Phase 1</div>
        <div className="text-mute text-sm max-w-xl">
          The backend route + data model for this page is already scaffolded in Phase 0.
          The UI body lands when the matching agent/route in Phase 1 ships. See <span className="font-mono text-ink">docs/ENGINEERING_ROADMAP.md</span>.
        </div>
      </Card>
    </AppShell>
  );
}
