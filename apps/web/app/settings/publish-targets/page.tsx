"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader } from "@/components/ui";
import { api, apiFetcher } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Target = {
  id: string;
  platform: string;
  mode: string;
  active: boolean;
  credentials: { configured: boolean; keys: string[] };
};

const PLATFORM_HINT: Record<string, string> = {
  x: '{"bearer_token": "AAA..."}',
  instagram: '{"access_token": "EAA...", "ig_user_id": "1784..."}',
  linkedin: '{"access_token": "AQ...", "author_urn": "urn:li:person:abc"}',
  pinterest: '{"access_token": "pina_...", "board_id": "1234"}',
  email: '{"api_key": "pk_live_...", "list_id": "ABC", "from_email": "hi@brand.com", "from_label": "Brand"}',
  webhook: '{"webhook_url": "https://example.com/hook", "secret": "shared-secret"}',
};

export default function Page() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [platform, setPlatform] = useState("x");
  const [creds, setCreds] = useState("");
  const [mode, setMode] = useState<"api" | "export">("api");
  useEffect(() => {
    setBrandId(getSelectedBrand());
    const h = () => setBrandId(getSelectedBrand());
    window.addEventListener("storage", h);
    return () => window.removeEventListener("storage", h);
  }, []);

  const { data, mutate } = useSWR<Target[]>(brandId ? `/brands/${brandId}/publish-targets` : null, apiFetcher);

  async function create() {
    if (!brandId) return;
    let credsObj: any = {};
    if (creds.trim()) {
      try { credsObj = JSON.parse(creds); } catch { toast.error("credentials must be valid JSON"); return; }
    }
    try {
      await api(`/brands/${brandId}/publish-targets`, {
        method: "POST",
        body: JSON.stringify({ platform, mode, credentials: credsObj, active: true }),
      });
      toast.success(`${platform} target created`);
      setCreds("");
      mutate();
    } catch (e: any) { toast.error(e.message); }
  }

  async function toggle(t: Target) {
    if (!brandId) return;
    try {
      await api(`/brands/${brandId}/publish-targets/${t.id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !t.active }),
      });
      mutate();
    } catch (e: any) { toast.error(e.message); }
  }

  async function remove(t: Target) {
    if (!brandId) return;
    try {
      await api(`/brands/${brandId}/publish-targets/${t.id}`, { method: "DELETE" });
      mutate();
    } catch (e: any) { toast.error(e.message); }
  }

  return (
    <AppShell>
      <PageHeader title="Publish Targets" description="One target per (brand, platform). Credentials are stored as JSON; the UI never echoes them back." />
      {!brandId && <Card className="p-8 text-mute text-sm">Select a brand in the top bar.</Card>}
      {brandId && (
        <>
          <Card className="p-4 mb-4">
            <div className="text-xs font-mono text-mute mb-3">ADD A TARGET</div>
            <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-start">
              <select value={platform} onChange={(e) => setPlatform(e.target.value)} className="rounded-xl bg-panel2 border border-line px-3 py-2 text-sm">
                {Object.keys(PLATFORM_HINT).map((p) => <option key={p}>{p}</option>)}
              </select>
              <select value={mode} onChange={(e) => setMode(e.target.value as any)} className="rounded-xl bg-panel2 border border-line px-3 py-2 text-sm">
                <option value="api">api</option>
                <option value="export">export</option>
              </select>
              <textarea
                value={creds}
                onChange={(e) => setCreds(e.target.value)}
                placeholder={PLATFORM_HINT[platform]}
                rows={3}
                className="md:col-span-3 rounded-xl border border-line bg-panel2 px-3 py-2 text-sm font-mono"
              />
              <Button onClick={create}>Save</Button>
            </div>
            <div className="text-xs text-mute mt-2">
              Tip: leave credentials blank to register an export-only fallback for that platform.
            </div>
          </Card>

          <Card className="overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-panel2 text-mute font-mono text-xs">
                <tr>
                  <th className="text-left p-3">Platform</th>
                  <th className="text-left p-3 w-24">Mode</th>
                  <th className="text-left p-3 w-44">Credentials</th>
                  <th className="text-left p-3 w-24">Active</th>
                  <th className="text-right p-3 w-44">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(data || []).map((t) => (
                  <tr key={t.id} className="border-t border-line">
                    <td className="p-3 font-mono">{t.platform}</td>
                    <td className="p-3 font-mono text-xs">{t.mode}</td>
                    <td className="p-3 text-xs">
                      {t.credentials.configured ? (
                        <span className="text-tennis">✓ {t.credentials.keys.join(", ")}</span>
                      ) : (
                        <span className="text-mute">none</span>
                      )}
                    </td>
                    <td className="p-3 text-xs">{t.active ? <span className="text-emerald-300">on</span> : <span className="text-mute">off</span>}</td>
                    <td className="p-3 text-right">
                      <Button variant="ghost" onClick={() => toggle(t)}>{t.active ? "Disable" : "Enable"}</Button>
                      <Button variant="ghost" onClick={() => remove(t)}>Delete</Button>
                    </td>
                  </tr>
                ))}
                {!data?.length && <tr><td colSpan={5} className="p-8 text-center text-mute">No targets yet — add one above.</td></tr>}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </AppShell>
  );
}
