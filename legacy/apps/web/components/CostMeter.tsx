"use client";

import useSWR from "swr";
import clsx from "clsx";
import { apiFetcher } from "@/lib/api";
import type { CostMeter as CM } from "@/lib/types";

export function CostMeter() {
  const { data } = useSWR<CM>("/orgs/me/cost", apiFetcher, { refreshInterval: 30000 });
  if (!data) return null;
  const tone =
    data.pct_used >= 90 ? "text-red-300" : data.pct_used >= 70 ? "text-amber-300" : "text-mute";
  return (
    <div className="hidden md:flex items-center gap-2 rounded-xl border border-line bg-panel2 px-3 py-1.5 text-xs font-mono">
      <span className="text-mute">MTD</span>
      <span className={clsx("font-medium", tone)}>${data.spent_usd.toFixed(2)}</span>
      <span className="text-mute">/</span>
      <span>${data.cap_usd.toFixed(0)}</span>
      <div className="ml-2 h-1.5 w-16 overflow-hidden rounded-full bg-line">
        <div
          className={clsx("h-full", data.pct_used >= 90 ? "bg-red-400" : data.pct_used >= 70 ? "bg-amber-400" : "bg-tennis")}
          style={{ width: `${Math.min(100, data.pct_used)}%` }}
        />
      </div>
    </div>
  );
}
