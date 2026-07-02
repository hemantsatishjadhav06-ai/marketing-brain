"use client";

import useSWR from "swr";
import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import clsx from "clsx";

import { apiFetcher } from "@/lib/api";
import { getSelectedBrand, setSelectedBrand } from "@/lib/brandStore";
import type { Brand } from "@/lib/types";

export function BrandSelector() {
  const { data: brands } = useSWR<Brand[]>("/brands", apiFetcher);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let s = getSelectedBrand();
    if (!s && brands && brands.length > 0) {
      s = brands[0].id;
      setSelectedBrand(s);
    }
    setSelected(s);
  }, [brands]);

  if (!brands || brands.length === 0) {
    return <div className="text-xs text-mute font-mono">no brands</div>;
  }

  const current = brands.find((b) => b.id === selected) || brands[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-xl border border-line bg-panel2 px-3 py-1.5 text-sm focus-ring"
      >
        <span className="inline-block size-2.5 rounded-full" style={{ background: current.accent_color }} />
        <span className="font-medium">{current.name}</span>
        <span className="text-mute font-mono text-xs uppercase">{current.sport}</span>
        <ChevronDown className="size-3.5 text-mute" />
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-64 rounded-xl border border-line bg-panel shadow-2xl z-50">
          {brands.map((b) => (
            <button
              key={b.id}
              onClick={() => {
                setSelectedBrand(b.id);
                setSelected(b.id);
                setOpen(false);
                window.location.reload();
              }}
              className={clsx(
                "flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-panel2",
                b.id === current.id && "bg-panel2"
              )}
            >
              <span className="inline-block size-2.5 rounded-full" style={{ background: b.accent_color }} />
              <span className="flex-1">{b.name}</span>
              <span className="text-xs text-mute font-mono uppercase">{b.sport}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
