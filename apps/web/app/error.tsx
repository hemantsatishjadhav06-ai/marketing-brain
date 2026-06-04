"use client";

// Global error boundary — Next.js app router fires this whenever a client
// component throws. Without it, the browser tab just blanks with
// "a client-side exception has occurred".

import { useEffect } from "react";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface to the console for easy copy-paste during bug reports.
    // eslint-disable-next-line no-console
    console.error("[marketing-brain] client error:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-aurora relative grid place-items-center px-6 py-10">
      <div className="glass rounded-xl p-8 max-w-xl w-full">
        <div className="text-[10px] uppercase tracking-widest text-mute font-mono">Client error</div>
        <h1 className="display text-3xl mt-2">Something on this page threw.</h1>
        <p className="text-ink2 text-sm mt-3">
          The rest of the cockpit is fine — only this view crashed. Common causes are a
          stale browser cache or a temporary network blip while loading data.
        </p>
        {error?.message && (
          <pre className="mt-4 text-xs bg-panel2 rounded-lg p-3 whitespace-pre-wrap font-mono text-red-300/90 overflow-auto max-h-48">
            {error.message}
            {error.digest && `\n\ndigest: ${error.digest}`}
          </pre>
        )}
        <div className="mt-5 flex gap-2">
          <button
            onClick={reset}
            className="rounded-xl accent-bg px-4 py-2 text-sm font-medium hover:opacity-90"
          >
            Try again
          </button>
          <Link
            href="/dashboard"
            className="rounded-xl border hairline px-4 py-2 text-sm hover:bg-panel2"
          >
            Back to Dashboard
          </Link>
          <button
            onClick={() => {
              if (typeof window !== "undefined") {
                window.location.reload();
              }
            }}
            className="rounded-xl border hairline px-4 py-2 text-sm hover:bg-panel2"
          >
            Hard refresh
          </button>
        </div>
        <div className="mt-6 text-[11px] text-mute font-mono">
          Open the browser console (⌥⌘I on Mac, F12 on Windows) for the full stack trace.
        </div>
      </div>
    </div>
  );
}
