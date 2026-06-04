"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Image as ImageIcon, Layers, Pin, Video, Mic, Film, FileText, Search,
  MessagesSquare, Twitter, ListOrdered, Megaphone, Mail, MessageCircle,
} from "lucide-react";

import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader, Skeleton, StatusPill } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type FieldKind = "text" | "textarea" | "select" | "number" | "product" | "switch";
type Field = {
  key: string; label: string; kind: FieldKind; required: boolean;
  placeholder: string; help: string; options: string[]; default: string;
};
type AgentMeta = {
  name: string; title: string; group: string; description: string;
  default_platform: string; default_content_type: string;
  icon: string; accent: string; fields: Field[];
};
type Product = { id: string; sku: string; title: string; price: number };
type RecentItem = { id: string; angle: string; platform: string; content_type: string; status: string; created_at: string };

const ICON: Record<string, any> = {
  Image: ImageIcon, Layers, Pin, Video, Mic, Film, FileText, Search,
  MessagesSquare, Twitter, ListOrdered, Megaphone, Mail, MessageCircle,
};

export default function CreateHubPage() {
  const router = useRouter();
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const { data: agents, isLoading: aLoading } = useSWR<AgentMeta[]>("/content/agents", apiFetcher);
  const { data: products } = useSWR<Product[]>(
    brandId ? `/brands/${brandId}/products` : null, apiFetcher,
  );
  const [active, setActive] = useState<string | null>(null);

  // pre-select first agent on load
  useEffect(() => {
    if (!active && agents && agents.length > 0) setActive(agents[0].name);
  }, [agents, active]);

  const groups = useMemo(() => {
    if (!agents) return [];
    const order = ["Visual", "Video", "Long-form", "Social", "Paid", "Direct"];
    return order.map((g) => ({ name: g, items: agents.filter((a) => a.group === g) })).filter((g) => g.items.length);
  }, [agents]);

  const meta = agents?.find((a) => a.name === active) || null;
  const { data: recent } = useSWR<RecentItem[]>(
    brandId && meta ? `/brands/${brandId}/content/search?q=${meta.default_content_type}&limit=5` : null,
    apiFetcher,
  );

  return (
    <AppShell>
      <PageHeader
        title="Create"
        description="Agency mode — fire any agent on demand without going through the calendar. Each tab is one agent with its own inputs and per-request overrides."
      />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar to start.</Card>}
      {brandId && (
        <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr_300px] gap-4">
          {/* LEFT: agent tabs grouped */}
          <div className="space-y-4">
            {aLoading && Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9 w-full rounded-lg" />)}
            {groups.map((g) => (
              <div key={g.name}>
                <div className="text-[10px] uppercase tracking-widest text-mute px-2 mb-1 font-mono">{g.name}</div>
                <div className="space-y-0.5">
                  {g.items.map((a) => {
                    const Icon = ICON[a.icon] || ImageIcon;
                    const isActive = a.name === active;
                    return (
                      <button
                        key={a.name}
                        onClick={() => setActive(a.name)}
                        className={`w-full flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-sm text-left transition ${
                          isActive ? "bg-panel2 text-ink accent-ring" : "text-mute hover:text-ink hover:bg-panel2"
                        }`}
                      >
                        <Icon className={`size-4 ${isActive ? "accent-text" : ""}`} strokeWidth={1.6} />
                        {a.title}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* CENTER: per-agent form */}
          {meta ? (
            <CreateForm meta={meta} brandId={brandId!} products={products || []} onCreated={(id) => router.push(`/studio/${id}`)} />
          ) : (
            <Card className="p-8 text-mute text-sm">Pick an agent on the left.</Card>
          )}

          {/* RIGHT: recent items by this agent type */}
          <div className="space-y-3">
            <Card className="p-4">
              <div className="text-xs font-mono text-mute mb-3">RECENT — {meta?.title || "—"}</div>
              {(!recent || recent.length === 0) && <div className="text-mute text-sm">No previous items of this type yet.</div>}
              <div className="space-y-2">
                {(recent || []).map((r) => (
                  <Link key={r.id} href={`/studio/${r.id}`}
                    className="block rounded-lg border hairline p-2 hover:bg-panel2 text-sm">
                    <div className="line-clamp-2">{r.angle}</div>
                    <div className="mt-1 flex items-center gap-2 text-[10px] font-mono">
                      <StatusPill status={r.status} />
                      <span className="text-mute">{r.platform}</span>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
            <Card className="p-4 text-xs text-mute">
              <div className="font-mono text-[10px] mb-2 uppercase tracking-widest">tip</div>
              Each tab is its own agent. The same brand voice + cross-sport guard apply everywhere — fire one or run the calendar, your choice.
            </Card>
          </div>
        </div>
      )}
    </AppShell>
  );
}


function CreateForm({
  meta, brandId, products, onCreated,
}: {
  meta: AgentMeta; brandId: string; products: Product[];
  onCreated: (contentItemId: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  // reset when agent changes
  useEffect(() => {
    const initial: Record<string, string> = {};
    for (const f of meta.fields) initial[f.key] = f.default || "";
    setValues(initial);
  }, [meta.name]);

  const set = (k: string, v: string) => setValues((s) => ({ ...s, [k]: v }));

  async function submit() {
    if (!values.angle || values.angle.trim().length < 2) {
      toast.error("Angle is required");
      return;
    }
    setSubmitting(true);
    try {
      const body: any = {
        brand_id: brandId,
        agent_name: meta.name,
        angle: values.angle,
        platform: values.platform || meta.default_platform,
        content_type: values.content_type || meta.default_content_type,
        product_id: values.product_id || undefined,
        overrides: {
          tone: values.override_tone || undefined,
          length: values.override_length || undefined,
          model: values.override_model || undefined,
          custom_instructions: values.override_custom_instructions || undefined,
        },
      };
      // drop empty overrides
      if (Object.values(body.overrides).every((v: any) => !v)) delete body.overrides;
      const r = await api<{ content_item_id: string }>("/content/create", {
        method: "POST",
        body: JSON.stringify(body),
      });
      toast.success(`${meta.title} created`);
      onCreated(r.content_item_id);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  // group fields: primary (required + non-override) vs overrides (advanced)
  const primaryFields = meta.fields.filter((f) => !f.key.startsWith("override_"));
  const overrideFields = meta.fields.filter((f) => f.key.startsWith("override_"));

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="display text-2xl">{meta.title}</h2>
          <p className="text-mute text-sm mt-1 max-w-xl">{meta.description}</p>
        </div>
        <span className="text-[10px] font-mono text-mute px-2 py-1 rounded bg-panel2 shrink-0">{meta.group}</span>
      </div>

      <div className="mt-5 space-y-3">
        {primaryFields.map((f) => (
          <FieldRow key={f.key} field={f} value={values[f.key] || ""} onChange={(v) => set(f.key, v)} products={products} />
        ))}
      </div>

      {overrideFields.length > 0 && (
        <details className="mt-6 group">
          <summary className="cursor-pointer text-xs font-mono text-mute uppercase tracking-widest hover:text-ink list-none flex items-center gap-2">
            <span className="text-accent">▸</span> Per-request overrides (advanced)
          </summary>
          <div className="mt-3 space-y-3 pl-2 border-l hairline">
            {overrideFields.map((f) => (
              <FieldRow key={f.key} field={f} value={values[f.key] || ""} onChange={(v) => set(f.key, v)} products={products} />
            ))}
          </div>
        </details>
      )}

      <div className="mt-6 flex items-center gap-3">
        <Button onClick={submit} disabled={submitting} size="lg">
          {submitting ? "Generating…" : `Generate ${meta.title}`}
        </Button>
        <span className="text-xs text-mute">
          Drafted into Studio · Critic + variant pass run automatically · cost-logged
        </span>
      </div>
    </Card>
  );
}


function FieldRow({
  field, value, onChange, products,
}: {
  field: Field; value: string; onChange: (v: string) => void; products: Product[];
}) {
  return (
    <div>
      <label className="text-[10px] uppercase tracking-widest text-mute font-mono">
        {field.label}{field.required && <span className="text-accent ml-1">*</span>}
      </label>
      {field.kind === "textarea" ? (
        <textarea
          value={value} onChange={(e) => onChange(e.target.value)}
          rows={3} placeholder={field.placeholder}
          className="mt-1 w-full rounded-xl border hairline bg-panel2 px-3.5 py-2 text-sm focus-ring"
        />
      ) : field.kind === "select" ? (
        <select
          value={value} onChange={(e) => onChange(e.target.value)}
          className="mt-1 w-full rounded-xl border hairline bg-panel2 px-3.5 py-2 text-sm focus-ring"
        >
          {!field.required && <option value="">—</option>}
          {field.options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : field.kind === "product" ? (
        <select
          value={value} onChange={(e) => onChange(e.target.value)}
          className="mt-1 w-full rounded-xl border hairline bg-panel2 px-3.5 py-2 text-sm focus-ring"
        >
          <option value="">— No product</option>
          {products.map((p) => <option key={p.id} value={p.id}>{p.sku} · {p.title}</option>)}
        </select>
      ) : field.kind === "number" ? (
        <Input type="number" value={value} onChange={(e) => onChange(e.target.value)} placeholder={field.placeholder} />
      ) : (
        <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={field.placeholder} />
      )}
      {field.help && <div className="text-[11px] text-mute mt-1">{field.help}</div>}
    </div>
  );
}
