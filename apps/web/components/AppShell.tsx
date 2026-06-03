"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import clsx from "clsx";
import {
  LayoutDashboard, Package, Brain, TrendingUp, Users, Lightbulb, Wand2,
  Calendar, Cpu, CheckSquare, FolderOpen, Send, BarChart3, Settings, LogOut,
} from "lucide-react";

import { apiFetcher, clearToken, getToken } from "@/lib/api";
import { BrandSelector } from "./BrandSelector";
import { CostMeter } from "./CostMeter";
import useSWR from "swr";
import type { Me } from "@/lib/types";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/brands", label: "Brands", icon: Brain },
  { href: "/products", label: "Products", icon: Package },
  { href: "/brand-brain", label: "Brand Brain", icon: Brain },
  { href: "/trends", label: "Trends", icon: TrendingUp },
  { href: "/audience", label: "Audience", icon: Users },
  { href: "/ideas", label: "Ideas", icon: Lightbulb },
  { href: "/studio", label: "Studio", icon: Wand2 },
  { href: "/calendar", label: "Calendar", icon: Calendar },
  { href: "/jobs", label: "Jobs", icon: Cpu },
  { href: "/reviews", label: "Reviews", icon: CheckSquare },
  { href: "/library", label: "Library", icon: FolderOpen },
  { href: "/publishing", label: "Publishing", icon: Send },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
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

  if (!ready) return null;

  return (
    <div className="grid grid-cols-[240px_1fr] min-h-screen">
      <aside className="border-r border-line bg-panel sticky top-0 h-screen flex flex-col">
        <div className="px-5 py-5 border-b border-line">
          <div className="flex items-center gap-2">
            <div className="grid grid-cols-2 gap-0.5">
              <span className="size-2 rounded-sm bg-tennis" />
              <span className="size-2 rounded-sm bg-padel" />
              <span className="size-2 rounded-sm bg-pickleball" />
              <span className="size-2 rounded-sm bg-badminton" />
            </div>
            <div className="font-serif text-lg leading-none">Marketing Brain</div>
          </div>
          <div className="text-xs text-mute mt-1 font-mono">v0.3 · phase 3</div>
        </div>
        <nav className="flex-1 px-2 py-3 overflow-y-auto">
          {NAV.map((n) => {
            const active = pathname?.startsWith(n.href);
            const Icon = n.icon;
            return (
              <Link
                key={n.href}
                href={n.href}
                className={clsx(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm",
                  active ? "bg-panel2 text-ink" : "text-mute hover:text-ink hover:bg-panel2"
                )}
              >
                <Icon className="size-4" />
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="px-3 py-3 border-t border-line text-xs">
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
        <header className="sticky top-0 z-30 border-b border-line bg-bg/80 backdrop-blur">
          <div className="flex items-center justify-between px-6 py-3">
            <div className="flex items-center gap-3">
              <BrandSelector />
              <span className="text-mute text-xs font-mono">→ Phase 3 · Native publishing</span>
            </div>
            <div className="flex items-center gap-3">
              <CostMeter />
            </div>
          </div>
        </header>
        <main className="px-6 py-6 max-w-screen-2xl w-full">{children}</main>
      </div>
    </div>
  );
}
