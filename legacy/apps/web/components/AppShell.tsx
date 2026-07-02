"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import {
  LayoutDashboard, Package, Brain, TrendingUp, Users, Lightbulb, Wand2,
  Calendar, Cpu, CheckSquare, FolderOpen, Send, BarChart3, Settings, LogOut,
  Sparkles,
} from "lucide-react";

import { apiFetcher, clearToken, getToken } from "@/lib/api";
import { BrandSelector } from "./BrandSelector";
import { CostMeter } from "./CostMeter";
import { SearchPalette } from "./SearchPalette";
import useSWR from "swr";
import type { Me } from "@/lib/types";

const NAV: Array<{ href: string; label: string; icon: any; group?: string }> = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, group: "Overview" },
  { href: "/brands", label: "Brands", icon: Brain, group: "Foundation" },
  { href: "/products", label: "Products", icon: Package, group: "Foundation" },
  { href: "/brand-brain", label: "Brand Brain", icon: Brain, group: "Foundation" },
  { href: "/trends", label: "Trends", icon: TrendingUp, group: "Foundation" },
  { href: "/audience", label: "Audience", icon: Users, group: "Foundation" },
  { href: "/create", label: "Create (any agent)", icon: Sparkles, group: "Create" },
  { href: "/ideas", label: "Ideas", icon: Lightbulb, group: "Create" },
  { href: "/studio", label: "Studio", icon: Wand2, group: "Create" },
  { href: "/calendar", label: "Calendar", icon: Calendar, group: "Create" },
  { href: "/jobs", label: "Jobs", icon: Cpu, group: "Create" },
  { href: "/reviews", label: "Reviews", icon: CheckSquare, group: "Ship" },
  { href: "/library", label: "Library", icon: FolderOpen, group: "Ship" },
  { href: "/publishing", label: "Publishing", icon: Send, group: "Ship" },
  { href: "/analytics", label: "Analytics", icon: BarChart3, group: "Learn" },
  { href: "/settings", label: "Settings", icon: Settings, group: "Org" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else setReady(true);
  }, [router]);

  const { data: me } = useSWR<Me>(ready ? "/auth/me" : null, apiFetcher);

  // theme injection (org-level white-label)
  const { data: theme } = useSWR<{ accent_color?: string; brand_name?: string; logo_url?: string; hide_powered_by?: boolean }>(
    ready ? "/orgs/me/theme" : null, apiFetcher,
  );
  useEffect(() => {
    if (theme?.accent_color) {
      document.documentElement.style.setProperty("--accent", theme.accent_color);
    }
  }, [theme?.accent_color]);

  if (!ready) return null;

  // group nav items
  const grouped: Record<string, typeof NAV> = {};
  NAV.forEach((n) => { (grouped[n.group || "—"] ||= []).push(n); });
  const groupOrder = ["Overview", "Foundation", "Create", "Ship", "Learn", "Org"];

  return (
    <div className="grid grid-cols-[260px_1fr] min-h-screen bg-bg">
      <aside className="border-r hairline bg-panel sticky top-0 h-screen flex flex-col">
        <div className="px-5 py-5 border-b hairline">
          <Link href="/" className="flex items-center gap-2.5">
            {theme?.logo_url ? (
              <img src={theme.logo_url} alt="" className="size-6 rounded" />
            ) : (
              <div className="grid grid-cols-2 gap-0.5">
                <span className="size-2 rounded-sm bg-tennis" />
                <span className="size-2 rounded-sm bg-padel" />
                <span className="size-2 rounded-sm bg-pickleball" />
                <span className="size-2 rounded-sm bg-badminton" />
              </div>
            )}
            <div className="display text-lg leading-none">{theme?.brand_name || "Marketing Brain"}</div>
          </Link>
          {!theme?.hide_powered_by && (
            <div className="text-[10px] text-mute mt-1 font-mono">v0.4 · phase 4</div>
          )}
        </div>
        <nav className="flex-1 px-2 py-3 overflow-y-auto">
          {groupOrder.map((g) => grouped[g] && (
            <div key={g} className="mb-3">
              <div className="text-[10px] uppercase tracking-widest text-mute px-3 mb-1 font-mono">{g}</div>
              {grouped[g].map((n) => {
                const active = pathname === n.href || pathname?.startsWith(n.href + "/");
                const Icon = n.icon;
                return (
                  <Link
                    key={n.href}
                    href={n.href}
                    className={clsx(
                      "flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-sm transition",
                      active ? "bg-panel2 text-ink accent-ring" : "text-mute hover:text-ink hover:bg-panel2",
                    )}
                  >
                    <Icon className="size-4" strokeWidth={1.6} />
                    {n.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="px-3 py-3 border-t hairline text-xs">
          <div className="font-mono text-mute truncate">{me?.email || "—"}</div>
          <div className="text-mute mt-0.5">role · <span className="text-ink">{me?.role || "—"}</span></div>
          <button
            className="mt-3 flex items-center gap-2 text-mute hover:text-ink"
            onClick={() => { clearToken(); router.replace("/login"); }}
          >
            <LogOut className="size-3.5" /> Log out
          </button>
        </div>
      </aside>

      <div className="flex flex-col">
        <header className="sticky top-0 z-30 border-b hairline bg-bg/75 backdrop-blur">
          <div className="flex items-center justify-between px-6 py-3">
            <div className="flex items-center gap-3">
              <BrandSelector />
              <span className="text-mute text-xs font-mono hidden md:inline">→ {theme?.brand_name || "Marketing Brain"} · v0.4</span>
            </div>
            <div className="flex items-center gap-3">
              <SearchPalette />
              <CostMeter />
            </div>
          </div>
        </header>
        <main className="px-6 py-6 max-w-screen-2xl w-full">{children}</main>
      </div>
    </div>
  );
}
