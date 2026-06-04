"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import {
  Image as ImageIcon, Layers, Pin, Video, Mic, Film, FileText, Search,
  MessagesSquare, Twitter, ListOrdered, Megaphone, Mail, MessageCircle, RefreshCcw,
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
type RecentItem = { id: string; angle: string; platform: string; content_type: string; status: string };
// /content/search returns { q, content_items: [...], ideas: [...] }
type SearchResp = { q: string; content_items: RecentItem[]; ideas: any[] };

const ICON: Record<string, any> = {
  Image: ImageIcon, Layers, Pin, Video, Mic, Film, FileText, Search,
  MessagesSquare, Twitter, ListOrdered, Megaphone, Mail, MessageCircle,
};

// Next.js requires useSearchParams in a Suspense boundary at prerender time.
export default function CreateHubPage() {
  return (
    <Suspense fallback={null}>
      <CreateHubInner />
    </Suspense>
  );
}

function CreateHubInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectProductId = searchParams?.get("product_id") || null;
  const preselectAgent = searchParams?.get("agent") || null;
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const { data: agentsResp, isLoading: aLoading } = useSWR<AgentMeta[] | { detail?: string }>("/content/agents", apiFetcher);
  const agents: AgentMeta[] = Array.isArray(agentsResp) ? agentsResp : [];
  const [active, setActive] = useState<string | null>(null);

  // pre-select agent — from ?agent= query param if valid, else first
  useEffect(() => {
    if (active || agents.length === 0) return;
    if (preselectAgent && agents.some((a) => a.name === preselectAgent)) {
      setActive(preselectAgent);
    } else {
      setActive(agents[0].name);
    }
  }, [agents, active, preselectAgent]);

  const groups = useMemo(() => {
    if (agents.length === 0) return [];
    const order = ["Visual", "Video", "Long-form", "Social", "Paid", "Direct"];
    return order.map((g) => ({ name: g, items: agents.filter((a) => a.group === g) })).filter((g) => g.items.length);
  }, [agents]);

  const meta = agents?.find((a) => a.name === active) || null;
  const { data: recentResp } = useSWR<SearchResp>(
    brandId && meta ? `/brands/${brandId}/content/search?q=${encodeURIComponent(meta.default_content_type)}&limit=5` : null,
    apiFetcher,
  );
  const recent: RecentItem[] = Array.isArray(recentResp?.content_items) ? recentResp!.content_items : [];

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
          {aLoading ? (
            <Card className="p-8 space-y-3">
              <Skeleton className="h-8 w-1/2 rounded" />
              <Skeleton className="h-4 w-3/4 rounded" />
              <Skeleton className="h-24 w-full rounded mt-4" />
              <Skeleton className="h-12 w-full rounded" />
              <Skeleton className="h-12 w-full rounded" />
            </Card>
          ) : meta ? (
            <CreateForm
              meta={meta}
              brandId={brandId!}
              preselectProductId={preselectProductId}
              onCreated={(id) => router.push(`/studio/${id}`)}
            />
          ) : agents.length === 0 ? (
            <Card className="p-8 text-mute text-sm">
              Couldn't load agents. Check the API is reachable at <span className="font-mono text-ink">/content/agents</span>.
            </Card>
          ) : (
            <Card className="p-8 text-mute text-sm">Pick an agent on the left.</Card>
          )}

          {/* RIGHT: recent items by this agent type */}
          <div className="space-y-3">
            <Card className="p-4">
              <div className="text-xs font-mono text-mute mb-3">RECENT — {meta?.title || "—"}</div>
              {recent.length === 0 && <div className="text-mute text-sm">No previous items of this type yet.</div>}
              <div className="space-y-2">
                {recent.map((r) => (
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
            {meta && (
              <Card className="p-4">
                <div className="text-[10px] font-mono text-mute uppercase tracking-widest mb-2">how this connects</div>
                <div className="text-xs space-y-1.5 font-mono">
                  <div className="text-mute">Form submits to:</div>
                  <div className="text-ink break-all">POST <span className="accent-text">/content/create</span></div>
                  <div className="text-mute mt-2">Dispatches to:</div>
                  <div className="text-ink">agents/<span className="accent-text">{meta.name}</span>.py</div>
                  <div className="text-mute mt-2">Renders into:</div>
                  <div className="text-ink">/studio/[id]</div>
                  <div className="text-mute mt-2">Pipeline:</div>
                  <div className="text-ink leading-relaxed">
                    create → agent.run() → Critic v2 → variants A/B → Studio
                  </div>
                </div>
              </Card>
            )}
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


type Category = { external_id: string; name: string; level: number; product_count: number };

function CreateForm({
  meta, brandId, preselectProductId, onCreated,
}: {
  meta: AgentMeta; brandId: string;
  preselectProductId?: string | null;
  onCreated: (contentItemId: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // reset when agent changes; apply preselect if any
  useEffect(() => {
    const initial: Record<string, string> = {};
    for (const f of meta.fields) initial[f.key] = f.default || "";
    if (preselectProductId) {
      initial.product_id = preselectProductId;
      setSelectedProductIds([preselectProductId]);
    } else {
      setSelectedProductIds([]);
    }
    setValues(initial);
  }, [meta.name, preselectProductId]);

  const set = (k: string, v: string) => setValues((s) => ({ ...s, [k]: v }));

  // categories (from Magento sync cache or demo seed)
  const SWR_OPTS = { revalidateOnFocus: true, revalidateOnReconnect: true, revalidateOnMount: true };
  const { data: categoriesResp, mutate: mutateCats } = useSWR<Category[] | { detail?: string }>(
    `/brands/${brandId}/integrations/magento/categories`, apiFetcher, SWR_OPTS,
  );
  const categories: Category[] = Array.isArray(categoriesResp)
    ? categoriesResp.filter((c) => c.product_count > 0).sort((a, b) => a.name.localeCompare(b.name))
    : [];

  // products — filtered by selected category if any
  const categoryName = categories.find((c) => c.external_id === values.category_id)?.name;
  const productsKey = `/brands/${brandId}/products${categoryName ? `?category=${encodeURIComponent(categoryName)}` : ""}`;
  const { data: productsResp, mutate: mutateProds } = useSWR<Product[] | { detail?: string }>(productsKey, apiFetcher, SWR_OPTS);
  const products: (Product & { image_urls?: string[] })[] = Array.isArray(productsResp) ? (productsResp as any) : [];
  function reload() { mutateCats(); mutateProds(); }

  const allowMulti = meta.fields.some((f) => f.key === "product_ids");

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
        overrides: {
          tone: values.override_tone || undefined,
          length: values.override_length || undefined,
          model: values.override_model || undefined,
          custom_instructions: values.override_custom_instructions || undefined,
        },
      };
      if (allowMulti && selectedProductIds.length > 0) {
        body.product_ids = selectedProductIds.slice(0, 5);
      } else if (values.product_id) {
        body.product_id = values.product_id;
      }
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

  function toggleProduct(id: string) {
    setSelectedProductIds((s) => {
      if (s.includes(id)) return s.filter((x) => x !== id);
      if (s.length >= 5) { toast.info("Max 5 products"); return s; }
      return [...s, id];
    });
  }

  // group fields: primary (required + non-override) vs overrides (advanced)
  const primaryFields = meta.fields.filter((f) => !f.key.startsWith("override_") && f.key !== "product_id" && f.key !== "product_ids" && f.key !== "category_id");
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

        {/* CATEGORY → PRODUCT cascade (Magento sync) */}
        <div>
          <label className="text-[10px] uppercase tracking-widest text-mute font-mono flex items-center justify-between">
            <span>Category (Magento) — filters products below</span>
            <button type="button" onClick={reload}
              className="inline-flex items-center gap-1 text-mute hover:text-ink normal-case tracking-normal">
              <RefreshCcw className="size-3" /> reload
            </button>
          </label>
          <select
            value={values.category_id || ""} onChange={(e) => set("category_id", e.target.value)}
            className="mt-1 w-full rounded-xl border hairline bg-panel2 px-3.5 py-2 text-sm focus-ring"
          >
            <option value="">— All categories ({products.length} products available)</option>
            {categories.map((c) => (
              <option key={c.external_id} value={c.external_id}>{c.name} ({c.product_count})</option>
            ))}
          </select>
          {categories.length === 0 && (
            <div className="text-[11px] text-mute mt-1">
              No Magento categories yet. <Link href="/settings/integrations" className="accent-text hover:underline">Connect Magento</Link>
              {" or "}
              <Link href="/products" className="accent-text hover:underline">seed demo products</Link>
              {" "}to populate this dropdown.
            </div>
          )}
        </div>

        {/* PRODUCT picker — single or multi depending on agent */}
        {!allowMulti && (
          <div>
            <label className="text-[10px] uppercase tracking-widest text-mute font-mono">
              Featured product (optional)
            </label>
            <select
              value={values.product_id || ""} onChange={(e) => set("product_id", e.target.value)}
              className="mt-1 w-full rounded-xl border hairline bg-panel2 px-3.5 py-2 text-sm focus-ring"
            >
              <option value="">— No product</option>
              {products.map((p) => <option key={p.id} value={p.id}>{p.sku} · {p.title}</option>)}
            </select>
            {values.product_id && (
              <ProductPreview product={products.find((p) => p.id === values.product_id)} />
            )}
          </div>
        )}
        {allowMulti && (
          <div>
            <label className="text-[10px] uppercase tracking-widest text-mute font-mono">
              Featured products — pick 1–5 ({selectedProductIds.length} selected)
            </label>
            <div className="mt-2 max-h-72 overflow-y-auto grid grid-cols-2 md:grid-cols-3 gap-2 rounded-xl border hairline bg-panel2 p-2">
              {products.length === 0 && <div className="col-span-full text-mute text-xs p-3">No products yet — sync Magento.</div>}
              {products.map((p) => {
                const checked = selectedProductIds.includes(p.id);
                const img = (p.image_urls || [])[0];
                return (
                  <button
                    key={p.id} type="button" onClick={() => toggleProduct(p.id)}
                    className={`flex gap-2 text-left rounded-lg p-1.5 border transition ${
                      checked ? "border-accent bg-panel3 accent-ring" : "hairline hover:bg-panel3"
                    }`}
                  >
                    {img ? <img src={img} alt="" className="size-12 rounded object-cover bg-bg2" /> : <div className="size-12 rounded bg-bg2" />}
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium line-clamp-2">{p.title}</div>
                      <div className="text-[10px] font-mono text-mute mt-0.5">{p.sku} · ${p.price}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
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


function ProductPreview({ product }: { product: any | undefined }) {
  if (!product) return null;
  const img = (product.image_urls || [])[0];
  return (
    <div className="mt-3 flex gap-3 items-center rounded-xl border hairline bg-panel2 p-2">
      {img ? <img src={img} alt="" className="size-16 rounded object-cover bg-bg2" />
           : <div className="size-16 rounded bg-bg2 grid place-items-center text-mute text-xs">no image</div>}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium line-clamp-2">{product.title}</div>
        <div className="text-xs font-mono text-mute mt-0.5">{product.sku} · ${product.price}{product.category ? ` · ${product.category}` : ""}</div>
      </div>
    </div>
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
