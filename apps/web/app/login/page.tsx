"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api, setToken } from "@/lib/api";
import { Button, Card, Input } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("owner@marketing-brain.local");
  const [password, setPassword] = useState("changeme");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(r.access_token);
      toast.success("Signed in");
      router.replace("/dashboard");
    } catch (err: any) {
      toast.error(err.message || "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid md:grid-cols-2 min-h-screen">
      <div className="flex flex-col justify-center px-10 md:px-20">
        <div className="max-w-sm w-full">
          <div className="font-serif text-4xl mb-1 tracking-tight">Marketing Brain</div>
          <div className="text-mute text-sm mb-8">AI content cockpit for racket-sport e-commerce.</div>
          <Card className="p-6">
            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="text-xs text-mute font-mono">EMAIL</label>
                <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
              </div>
              <div>
                <label className="text-xs text-mute font-mono">PASSWORD</label>
                <Input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
              </div>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          </Card>
          <div className="text-xs text-mute mt-4 font-mono">
            Default: owner@marketing-brain.local / changeme — override in .env before going live.
          </div>
        </div>
      </div>
      <div className="hidden md:block relative overflow-hidden bg-panel border-l border-line">
        <div className="absolute inset-0 grid grid-cols-5 grid-rows-5 gap-1 p-6 opacity-60">
          {Array.from({ length: 25 }).map((_, i) => (
            <div key={i} className="rounded bg-panel2" />
          ))}
        </div>
        <div className="relative h-full flex flex-col justify-end p-10">
          <div className="grid grid-cols-5 gap-2 mb-6">
            <span className="h-2 rounded-sm bg-tennis" />
            <span className="h-2 rounded-sm bg-padel" />
            <span className="h-2 rounded-sm bg-pickleball" />
            <span className="h-2 rounded-sm bg-badminton" />
            <span className="h-2 rounded-sm bg-squash" />
          </div>
          <div className="font-serif text-2xl leading-snug max-w-md">
            One brain. Five sports. Zero crossover.
            <span className="block text-mute text-base mt-2">
              Tennis, padel, pickleball, badminton, squash — each its own isolated vertical.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
