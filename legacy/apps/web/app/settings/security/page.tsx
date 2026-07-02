"use client";

import { useState } from "react";
import { toast } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Input, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

export default function Page() {
  const [secret, setSecret] = useState("");
  const [otpauth, setOtpauth] = useState("");
  const [code, setCode] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [stage, setStage] = useState<"idle" | "setup" | "confirm">("idle");

  async function setup() {
    try {
      const r = await api<{ secret: string; otpauth_url: string; already_enabled?: boolean }>("/auth/2fa/setup", { method: "POST" });
      if (r.already_enabled) {
        setEnabled(true);
        toast.info("2FA is already enabled on this account");
        return;
      }
      setSecret(r.secret);
      setOtpauth(r.otpauth_url);
      setStage("setup");
    } catch (e: any) { toast.error(e.message); }
  }
  async function enable() {
    try {
      await api("/auth/2fa/enable", { method: "POST", body: JSON.stringify({ code }) });
      setEnabled(true);
      setStage("idle");
      toast.success("2FA enabled");
    } catch (e: any) { toast.error(e.message); }
  }
  async function disable() {
    try {
      await api("/auth/2fa/disable", { method: "POST", body: JSON.stringify({ code }) });
      setEnabled(false);
      toast.success("2FA disabled");
    } catch (e: any) { toast.error(e.message); }
  }

  const qrUrl = otpauth
    ? `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(otpauth)}`
    : "";

  return (
    <AppShell>
      <PageHeader title="Security" description="Time-based one-time-password (TOTP) two-factor for sign-in." />
      <Card className="p-6 max-w-xl">
        <div className="text-xs font-mono text-mute mb-3">TWO-FACTOR AUTHENTICATION</div>
        {!enabled && stage === "idle" && (
          <>
            <p className="text-sm text-ink2">Use an authenticator app (1Password, Authy, Google Authenticator) to add a 6-digit code at sign-in.</p>
            <Button onClick={setup} className="mt-4">Set up 2FA</Button>
          </>
        )}
        {stage === "setup" && (
          <div className="space-y-4">
            <p className="text-sm text-ink2">Scan the QR with your authenticator app, then enter the 6-digit code to confirm.</p>
            <div className="flex gap-5 items-start">
              {qrUrl && <img src={qrUrl} alt="QR code" className="rounded-lg bg-white p-2" />}
              <div className="text-xs font-mono text-mute break-all">
                <div className="text-[10px] uppercase tracking-widest mb-1">Secret (manual entry)</div>
                <div>{secret}</div>
              </div>
            </div>
            <Input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="123 456" />
            <Button onClick={enable}>Verify + enable</Button>
          </div>
        )}
        {enabled && (
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 text-sm text-good"><span className="size-2 rounded-full bg-good"/> 2FA is enabled</div>
            <p className="text-sm text-mute">Enter a current 6-digit code to disable.</p>
            <Input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="123 456" />
            <Button variant="danger" onClick={disable}>Disable 2FA</Button>
          </div>
        )}
      </Card>
    </AppShell>
  );
}
