"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import { getSelectedBrand } from "@/lib/brandStore";

type Hit =
  | { kind: "content"; id: string; platform: string; content_type: string; angle: string; status: string }
  | { kind: "idea"; id: string; title: string; angle: string; score: number; platform: string; content_type: string };

export function SearchPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ content_items: Hit[]; ideas: Hit[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // ⌘K / Ctrl-K to open
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  // debounce search
  useEffect(() => {
    if (!open) return;
    if (q.trim().length < 2) { setHits(null); return; }
    const brandId = getSelectedBrand();
    if (!brandId) return;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await api<{ content_items: Hit[]; ideas: Hit[] }>(
          `/brands/${brandId}/content/search?q=${encodeURIComponent(q)}&limit=20`,
        );
        setHits(r);
      } catch { setHits(null); }
      finally { setLoading(false); }
    }, 180);
    return () => clearTimeout(t);
  }, [q, open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="hidden md:flex items-center gap-2 rounded-xl border hairline bg-panel2 px-3 py-1.5 text-xs text-mute hover:text-ink hover:bg-panel3 transition"
      >
        <Search className="size-3.5" />
        <span>Search content</span>
        <span className="ml-2 font-mono opacity-70">⌘K</span>
      </button>
      {open && (
        <div className="fixed inset-0 z-50 grid place-items-start pt-24 bg-bg/70 backdrop-blur-sm" onClick={() => setOpen(false)}>
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-xl mx-auto glass rounded-xl shadow-soft overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3 border-b hairline">
              <Search className="size-4 text-mute" />
              <input
                ref={inputRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search content + ideas in this brand…"
                className="flex-1 bg-transparent outline-none text-sm"
              />
              <kbd className="text-[10px] font-mono text-mute">esc</kbd>
            </div>
            <div className="max-h-[60vh] overflow-y-auto">
              {loading && <div className="p-4 text-sm text-mute">Searching…</div>}
              {!loading && q.length < 2 && (
                <div className="p-4 text-sm text-mute">Type 2+ characters to search content + ideas.</div>
              )}
              {!loading && hits && hits.content_items.length === 0 && hits.ideas.length === 0 && (
                <div className="p-4 text-sm text-mute">No matches.</div>
              )}
              {hits && hits.content_items.length > 0 && (
                <div className="p-2">
                  <div className="text-[10px] font-mono text-mute uppercase tracking-widest px-2 py-1">Content</div>
                  {hits.content_items.map((h: any) => (
                    <Link key={h.id} href={`/studio/${h.id}`} onClick={() => setOpen(false)}
                      className="block px-2 py-2 rounded hover:bg-panel2">
                      <div className="text-sm line-clamp-1">{h.angle}</div>
                      <div className="text-[10px] font-mono text-mute">{h.platform} · {h.content_type} · {h.status}</div>
                    </Link>
                  ))}
                </div>
              )}
              {hits && hits.ideas.length > 0 && (
                <div className="p-2 border-t hairline">
                  <div className="text-[10px] font-mono text-mute uppercase tracking-widest px-2 py-1">Ideas</div>
                  {hits.ideas.map((h: any) => (
                    <Link key={h.id} href="/ideas" onClick={() => setOpen(false)}
                      className="block px-2 py-2 rounded hover:bg-panel2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono accent-text text-xs w-10 text-right">{h.score.toFixed(0)}</span>
                        <span className="text-sm line-clamp-1 flex-1">{h.title || h.angle}</span>
                      </div>
                      <div className="text-[10px] font-mono text-mute ml-12">{h.platform} · {h.content_type}</div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
