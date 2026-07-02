"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api, setToken } from "@/lib/api";

const SPORTS = [
  { name: "Tennis", color: "#CCFF00" },
  { name: "Padel", color: "#22D3EE" },
  { name: "Pickleball", color: "#F59E0B" },
  { name: "Badminton", color: "#A78BFA" },
  { name: "Squash", color: "#EF4444" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("owner@marketing-brain.local");
  const [password, setPassword] = useState("changeme");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState<"creds" | "2fa">("creds");
  const [userId, setUserId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      if (stage === "creds") {
        const r = await api<any>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
        if (r.requires_2fa) {
          setUserId(r.user_id);
          setStage("2fa");
          toast.info("Enter your 6-digit code");
        } else {
          setToken(r.access_token);
          toast.success("Signed in");
          router.replace("/dashboard");
        }
      } else {
        const r = await api<{ access_token: string }>("/auth/2fa/verify-login", {
          method: "POST",
          body: JSON.stringify({ user_id: userId, code }),
        });
        setToken(r.access_token);
        toast.success("Signed in");
        router.replace("/dashboard");
      }
    } catch (err: any) {
      toast.error(err.message || "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-aurora relative overflow-hidden">
      <div className="noise absolute inset-0" />
      <div className="relative max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="grid grid-cols-2 gap-0.5">
            {SPORTS.slice(0, 4).map((s) => (
              <span key={s.name} className="size-2 rounded-sm" style={{ background: s.color }} />
            ))}
          </div>
          <span className="display text-lg">Marketing Brain</span>
        </Link>
        <Link href="/" className="text-sm text-mute hover:text-ink">← Back to site</Link>
      </div>

      <div className="grid lg:grid-cols-2 items-center max-w-6xl mx-auto px-6 pt-10 lg:pt-20 pb-20 gap-12">
        <div className="hidden lg:block">
          <h1 className="display display-tight text-5xl lg:text-6xl leading-[1.05]">
            One brain.<br /><span className="accent-text">Five sports.</span> Zero crossover.
          </h1>
          <p className="text-ink2 mt-6 text-lg max-w-md">
            Tennis · padel · pickleball · badminton · squash — each its own isolated vertical with its own brand voice, calendar, and publish targets.
          </p>
          <div className="flex flex-wrap gap-2 mt-8">
            {SPORTS.map((s) => (
              <span key={s.name} className="rounded-full px-3 py-1 text-xs font-mono glass" style={{ color: s.color }}>
                ● {s.name}
              </span>
            ))}
          </div>
        </div>

        <div className="max-w-md w-full mx-auto">
          <div className="glass rounded-xl p-7 shadow-soft fade-up">
            <div className="display text-3xl">{stage === "creds" ? "Welcome back" : "Two-factor"}</div>
            <div className="text-mute text-sm mt-1">
              {stage === "creds" ? "Sign in to your cockpit." : "Enter the 6-digit code from your authenticator app."}
            </div>
            <form onSubmit={submit} className="space-y-4 mt-6">
              {stage === "creds" ? (
                <>
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-mute font-mono">Email</label>
                    <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required
                      className="mt-1 w-full rounded-xl border hairline bg-panel2 px-3.5 py-2.5 text-ink placeholder-mute focus-ring" />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-mute font-mono">Password</label>
                    <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required
                      className="mt-1 w-full rounded-xl border hairline bg-panel2 px-3.5 py-2.5 text-ink focus-ring" />
                  </div>
                </>
              ) : (
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-mute font-mono">6-digit code</label>
                  <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    inputMode="numeric" maxLength={6} required autoFocus
                    className="mt-1 w-full rounded-xl border hairline bg-panel2 px-3.5 py-3 text-ink text-center text-3xl tracking-[0.5em] font-mono focus-ring" />
                </div>
              )}
              <button type="submit" disabled={loading}
                className="w-full rounded-xl py-3 font-medium accent-bg hover:opacity-90 shadow-glow disabled:opacity-50 transition">
                {loading ? "…" : (stage === "creds" ? "Sign in →" : "Verify")}
              </button>
              {stage === "2fa" && (
                <button type="button" onClick={() => setStage("creds")} className="w-full text-xs text-mute hover:text-ink">
                  ← Back to login
                </button>
              )}
            </form>
          </div>
          <div className="text-xs text-mute mt-4 font-mono text-center">
            Default: owner@marketing-brain.local / changeme
          </div>
        </div>
      </div>
    </div>
  );
}
